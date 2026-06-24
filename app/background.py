import asyncio
import datetime
import subprocess
import uuid
from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, models
from app.database import async_session
from app.services import google_workspace, ai

# 이미 알림을 보낸 일정 ID들을 보관해 중복 알림을 방지하는 메모리 셋
# (상용 Redis/메모리 캐시 대신 단순 메모리 구조 활용)
notified_events = set()

# ==========================================
# 네트워크 환경 분석: 모바일 핫스팟 감지
# ==========================================

def check_hotspot_connection() -> bool:
    """Windows 무선 인터페이스 정보를 검사하여 모바일 핫스팟 전환 여부를 감지합니다."""
    try:
        # Windows OS 명령어를 실행해 WLAN 연결 상태를 조회합니다.
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            encoding="cp949", # 한글 Windows 인코딩 대응
            timeout=2.0
        )
        
        output = result.stdout.lower()
        
        # Wi-Fi SSID 행을 파싱하여 핫스팟 연관 키워드를 매칭합니다.
        ssid_line = ""
        for line in output.split("\n"):
            if "ssid" in line and "bssid" not in line:
                ssid_line = line
                break
                
        if ssid_line:
            ssid_name = ssid_line.split(":")[-1].strip()
            # 모바일 핫스팟에 주로 쓰이는 키워드 필터링
            hotspot_keywords = ["hotspot", "iphone", "galaxy", "mobile", "androidhotspot", "테더링", "핫스팟"]
            if any(kw in ssid_name for kw in hotspot_keywords):
                print(f"[Hotspot Detected] Active Wifi SSID: {ssid_name}")
                return True
                
        return False
    except Exception as e:
        # 예외 상황 및 개발 기기 환경(이더넷 전용 등)인 경우 기본 False 반환
        print(f"[Hotspot Check Fallback] Wifi interface check skipped: {e}")
        return False

# ==========================================
# 백그라운드 모니터링 무한 비동기 루프
# ==========================================

async def background_monitor_loop():
    """매 60초마다 실행되는 무한 비동기 루프로 시스템을 진단하여 경고 알림을 적재합니다."""
    print("[Background Monitor] Starting monitor loop...")
    while True:
        try:
            # 매 루프마다 신규 독립 DB 세션을 열어 메모리 누수를 원천 차단합니다.
            async with async_session() as db:
                # 1. 시스템 내 모든 등록 유저 조회
                stmt = select(models.User)
                res = await db.execute(stmt)
                users = res.scalars().all()
                
                now = datetime.datetime.now()
                
                for user in users:
                    user_id = user.id
                    
                    # --- 1) 캘린더 리마인더 체크 (시작 15분 미만 전 일정) ---
                    try:
                        events = await google_workspace.get_today_calendar(user_id)
                        for ev in events:
                            start_str = ev.get("start")
                            summary = ev.get("summary", "일정")
                            if not start_str:
                                continue
                                
                            # '2026-06-24T12:00:00' 포맷 파싱 (타임존 정보 제거 후 비교)
                            try:
                                # T 문자 구분 및 타임존 offset 잘라내기
                                clean_start = start_str.split("+")[0].split("Z")[0]
                                start_dt = datetime.datetime.fromisoformat(clean_start)
                            except ValueError:
                                continue
                                
                            time_diff = start_dt - now
                            diff_minutes = time_diff.total_seconds() / 60.0
                            
                            # 시작까지 15분 미만으로 남은 임박한 일정이면서, 과거에 알리지 않은 건
                            event_key = f"{user_id}_{summary}_{start_str}"
                            if 0 < diff_minutes < 15 and event_key not in notified_events:
                                msg = f"일정 임박 경고: '{summary}' 일정이 약 {int(diff_minutes)}분 뒤에 시작됩니다."
                                await crud.create_notification(db, user_id, "CALENDAR_REMINDER", msg)
                                notified_events.add(event_key)
                                print(f"[Alert Generated] Calendar alert for {user_id}: {summary}")
                    except Exception as ex:
                        print(f"[Monitor Error] Calendar check failed for user {user_id}: {ex}")
                        

                        
                    # --- 3) 모바일 핫스팟 네트워크 전환 감지 ---
                    try:
                        if check_hotspot_connection():
                            msg = "네트워크 전환 감지: 모바일 핫스팟 테더링 환경으로 연결이 전환되었습니다. 데이터 요금 초과에 주의하십시오."
                            
                            # 알림이 너무 연속적으로 적재되지 않도록 최신 알림 중 동일 타입 확인
                            recent_notifs = await crud.get_notifications(db, user_id, limit=1)
                            if not recent_notifs or recent_notifs[0].type != "HOTSPOT_DETECTED" or (now - recent_notifs[0].created_at).total_seconds() > 300:
                                await crud.create_notification(db, user_id, "HOTSPOT_DETECTED", msg)
                                print(f"[Alert Generated] Hotspot warning for {user_id}")
                    except Exception as ex:
                        print(f"[Monitor Error] Hotspot check failed for user {user_id}: {ex}")
                        
                # 루프 트랜잭션 정상 커밋
                await db.commit()
                
        except Exception as e:
            print(f"[Background Monitor Fatal] Loop cycle error: {e}")
            
        # 매 60초 대기
        await asyncio.sleep(60)

# ==========================================
# 최초 접속 일일 브리핑 텍스트 생성
# ==========================================

async def generate_daily_briefing_text(user_id: uuid.UUID) -> str:
    """당일 최초 접속 시 동작하며 날짜, 날씨, 일정, 메일, IoT 전력 상태 정보를

    Gemini AI 모델로 결합하여 자연스러운 일일 브리핑 구어체 스크립트를 작성합니다.
    """
    now = datetime.datetime.now()
    today_str = now.strftime("%Y년 %m월 %d일")
    
    # 1. 캘린더 일정 수집
    events = await google_workspace.get_today_calendar(user_id)
    events_summary = ""
    if events:
        events_summary = "\n오늘의 일정:\n" + "\n".join([f"- {ev['summary']} ({ev['start']} ~ {ev['end']})" for ev in events])
    else:
        events_summary = "\n오늘 등록된 구글 캘린더 일정이 없습니다."
        
    # 2. Gmail 안읽은 메일 5개 스니펫 수집
    emails = await google_workspace.get_unread_emails(user_id)
    emails_summary = ""
    if emails:
        emails_summary = "\n읽지 않은 이메일 목록:\n" + "\n".join([f"- 보낸이: {em['sender']} / 제목: {em['subject']}" for em in emails])
    else:
        emails_summary = "\n읽지 않은 새 메일이 없습니다."
        
    # 3. IoT 기기 상태 수집 비활성화 (기능 삭제)
    devices_summary = ""
            
    # 4. 날씨 정보 수집 (모의 정보 활용)
    weather_info = "현재 기온은 25도이며 대체로 맑고 포근한 날씨입니다. 오후 3시쯤 소나기 예보가 있으니 외출 시 우산을 챙기시기 바랍니다."

    # 5. Gemini 2.5-flash 프롬프트 조립
    prompt = (
        f"당신은 ARGOS 시스템의 개인 음성 비서입니다. 아래의 원시 정보를 토대로 "
        f"사용자가 아침에 듣기에 가장 자연스럽고 정중하며 상냥한 말투(구어체 존댓말)의 "
        f"일일 요약 브리핑 대본 텍스트를 작성해 주세요.\n\n"
        f"[정보 데이터]\n"
        f"- 오늘 날짜: {today_str}\n"
        f"- 날씨 정보: {weather_info}\n"
        f"{events_summary}\n"
        f"{emails_summary}\n"
        f"{devices_summary}\n"
    )
    
    client = ai.get_gemini_client()
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        print(f"[Daily Briefing Gen Error] {e}")
        # 오류 발생 시 기본 Fallback 브리핑 스크립트 반환
        return (
            f"안녕하셨습니까? {today_str} 아침 브리핑입니다. 오늘 캘린더 일정은 총 {len(events)}건이 있으며, "
            f"읽지 않은 Gmail 메일이 {len(emails)}건 도착해 있습니다. "
            f"오늘도 행복하고 안전한 하루 보내십시오."
        )
