import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header, HTTPException, UploadFile, File, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional

from app import models, schemas, crud
from app.database import engine, Base, get_db
from app.services import ai, google_workspace, voice, orchestrator
from app.background import background_monitor_loop, generate_daily_briefing_text

# ==========================================
# FastAPI Lifespan (애플리케이션 수명 주기 관리)
# ==========================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 애플리케이션 시작 시 데이터베이스 초기화 및 pgvector 활성화 시도
    print("[Lifespan Startup] Initializing Database & pgvector...")
    try:
        async with engine.begin() as conn:
            try:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                print("[Lifespan Startup] Enabled pgvector extension successfully.")
            except Exception as e:
                print(f"[Lifespan Startup Warning] pgvector activation bypassed: {e}")
            
            # 테이블 생성
            await conn.run_sync(Base.metadata.create_all)
            print("[Lifespan Startup] Database tables created.")
            from app import database
            database.IS_DB_ONLINE = True
    except Exception as db_err:
        print(f"[Lifespan Startup Warning] Database connection failed: {db_err}")
        print("[Lifespan Startup Warning] Running in offline mode with In-Memory fallback database.")
        from app import database
        database.IS_DB_ONLINE = False


    # 2. 백그라운드 모니터링 태스크 루프 기동
    monitor_task = asyncio.create_task(background_monitor_loop())
    print("[Lifespan Startup] Background monitor loop started.")
    
    yield
    
    # 3. 애플리케이션 종료 시 리소스 해제 및 백그라운드 태스크 종료
    print("[Lifespan Shutdown] Canceling background monitor loop...")
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    print("[Lifespan Shutdown] Cleanup complete.")

app = FastAPI(
    title="ARGOS Backend System API",
    version="1.0.0",
    description="FastAPI-based secure multi-tenant assistant backend for project ARGOS.",
    lifespan=lifespan
)

from fastapi.middleware.cors import CORSMiddleware

# React 개발 서버 및 외부 통신 허용을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# 멀티테넌트 데이터 격리 강제를 위한 공통 의존성 정의
# ==========================================
async def get_current_user_id(
    x_user_id: str = Header(..., description="인증된 사용자의 고유 ID (UUID 포맷)")
) -> uuid.UUID:
    """모든 API 요청에서 X-User-Id 헤더를 검사하고 파싱하여 사용자 고유 ID를 반환합니다.

    이를 통해 테넌트 데이터 격리를 완벽하게 준수합니다.
    """
    try:
        return uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바르지 않은 User ID 형식입니다. (UUID 포맷 헤더 'X-User-Id' 필요)"
        )

# ==========================================
# API 라우터 엔드포인트 정의
# ==========================================

# 1. 사용자 계정 생성 (테스트 및 테넌트 초기화용)
@app.post("/api/v1/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def create_new_user(user_in: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(models.select(models.User).where(models.User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="이미 등록된 이메일 주소입니다.")
    new_user = await crud.create_user(db, email=user_in.email)
    return new_user

@app.put("/api/v1/users/profile", status_code=status.HTTP_200_OK)
async def update_profile(
    profile_in: schemas.ProfileUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    profile = await crud.update_user_profile(db, user_id, profile_in.profile_data)
    if not profile:
        raise HTTPException(status_code=404, detail="사용자 정보를 찾을 수 없습니다.")
    return {"message": "프로필 정보가 업데이트되었습니다.", "profile_data": profile.profile_data}

# 2. [모듈 1: AI 대화 및 지능형 가이드]
@app.post("/api/v1/ai/chat", response_model=schemas.ChatResponse)
async def ai_chat(
    request: schemas.ChatRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    result = await ai.execute_ai_chat(user_id, request.query, db)
    return result

@app.post("/api/v1/ai/tts-reformat")
async def tts_reformat(request: schemas.ChatRequest):
    """300자 이상의 문장에 대한 TTS 최적화 요약을 재가공합니다."""
    tts_text = await ai.get_tts_text(request.query)
    return {"tts_response": tts_text}

# 3. [모듈 2: Google Workspace 연동 비서]
@app.get("/api/v1/google/calendar")
async def get_calendar(
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    events = await google_workspace.get_today_calendar(user_id)
    return {"events": events}

@app.post("/api/v1/google/calendar/create")
async def create_calendar(
    event_in: schemas.CalendarEventCreate,
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    res = await google_workspace.Calendar(
        user_id=user_id,
        summary=event_in.summary,
        start_time=event_in.start_time,
        end_time=event_in.end_time
    )
    return res

@app.get("/api/v1/google/gmail/unread")
async def get_gmail_unread(
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    emails = await google_workspace.get_unread_emails(user_id)
    return {"emails": emails}

@app.post("/api/v1/google/sheets/append")
async def append_sheet(
    req: schemas.SpreadsheetAppendRequest,
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    res = await google_workspace.append_sheet_data(user_id, req.spreadsheet_id, req.row_data)
    return res

@app.get("/api/v1/google/drive/search")
async def search_drive(
    keyword: str = Query(...),
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    files = await google_workspace.search_drive_files(user_id, keyword)
    return {"files": files}

@app.get("/api/v1/google/drive/read/{file_id}")
async def read_drive_file(
    file_id: str,
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    content = await google_workspace.read_drive_file_content(user_id, file_id)
    return {"content": content}

# 4. [모듈 3: 바이오메트릭 성문 보안 및 음성 스트레스 분석]
@app.post("/api/v1/voice/register")
async def voice_register(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    audio_bytes = await file.read()
    # 40차원 MFCC 특징 추출
    mfcc_features = voice.extract_mfcc_frames(audio_bytes)
    
    # 성문 데이터베이스에 신규 등록 (기본 임계치 70.0 설정)
    await crud.register_voice(db, user_id, mfcc_features.tolist(), threshold=70.0)
    return {
        "status": "success",
        "message": "바이오메트릭 성문 프로필이 등록되었습니다.",
        "mfcc_shape": mfcc_features.shape
    }

@app.post("/api/v1/voice/verify")
async def voice_verify(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    audio_bytes = await file.read()
    # DTW 분석 및 임계값 자동 조정
    res = await voice.calculate_voice_similarity(user_id, audio_bytes, db)
    return res

@app.post("/api/v1/voice/stress-analysis")
async def voice_stress_analysis(
    file: UploadFile = File(...)
):
    audio_bytes = await file.read()
    # 목소리 Jitter, Shimmer, F0 파라미터 감정 진단
    analysis = voice.analyze_voice_emotion(audio_bytes)
    return analysis

@app.post("/api/v1/audio/ai_chat_voice")
async def ai_chat_voice(
    file: UploadFile = File(...),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """오디오 바이트를 수신하여 성문 인증, 스트레스 및 감정 분석, 그리고 AI 대화를 통합적으로 연동 실행합니다."""
    audio_bytes = await file.read()
    
    # 1. 성문 매칭 (DTW)
    verify_res = await voice.calculate_voice_similarity(user_id, audio_bytes, db)
    
    # 2. 감정 및 스트레스 분석
    stress_res = voice.analyze_voice_emotion(audio_bytes)
    
    # 3. AI 대화 실행 (성문 인증 성공 시에만)
    chat_res = None
    if verify_res.get("verified", False):
        # 모의 STT (전송된 음성이 가습기 스위치 제어 쿼리로 매칭되었다고 상정)
        query_text = "서재 가습기 플러그 상태 확인하고 켜줘"
        chat_res = await ai.execute_ai_chat(user_id, query_text, db)
    else:
        chat_res = {
            "response": "성문 보안 등급이 일치하지 않아 작업을 진행할 수 없습니다. 다시 시도해 주십시오.",
            "tts_response": "성문 보안 등급이 일치하지 않아 작업을 진행할 수 없습니다.",
            "function_called": False
        }
        
    return {
        "verified": verify_res.get("verified", False),
        "verification_details": verify_res,
        "stress_details": stress_res,
        "chat_details": chat_res
    }


# 5. [모듈 4: 태스크 오케스트레이션 및 상담 자동화]
@app.post("/api/v1/orchestration/run", response_model=schemas.OrchestrationResponse)
async def orchestration_run(
    req: schemas.OrchestrationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    res = await orchestrator.run_orchestrated_scenario(
        user_id=user_id,
        scenario_name=req.scenario_name,
        user_approval=req.user_approval,
        db=db
    )
    return res

@app.post("/api/v1/orchestration/consultation")
async def consultation_note(
    req: schemas.ConsultationRequest,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    res = await orchestrator.save_consultation_note(user_id, req.raw_text, db)
    return res



@app.get("/api/v1/daily-briefing")
async def daily_briefing(
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    briefing_text = await generate_daily_briefing_text(user_id)
    return {"briefing_text": briefing_text}

@app.get("/api/v1/notifications")
async def get_system_notifications(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """백그라운드 진단 모니터 루틴이 발생시킨 유저 고유 경고 알림 리스트를 조회합니다."""
    notifs = await crud.get_notifications(db, user_id)
    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "message": n.message,
                "created_at": n.created_at.isoformat()
            } for n in notifs
        ]
    }

@app.get("/api/v1/settings/integrations", response_model=List[schemas.ApiIntegrationResponse])
async def get_integrations(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """사용자가 등록한 API 서비스 목록을 조회합니다. 실제 키 값은 sk-******** 형태로 마스킹 처리하여 반환합니다."""
    integrations = await crud.get_user_api_integrations(db, user_id)
    response_list = []
    
    from app.config import decrypt_token
    for item in integrations:
        try:
            decrypted = decrypt_token(item.encrypted_api_key)
            prefix = decrypted[:3] if len(decrypted) > 3 else "key"
            masked = f"sk-{prefix}********"
        except Exception:
            masked = "sk-********"
            
        response_list.append(
            schemas.ApiIntegrationResponse(
                id=item.id,
                service_name=item.service_name,
                masked_key=masked,
                created_at=item.created_at,
                updated_at=item.updated_at
            )
        )
    return response_list

@app.post("/api/v1/settings/integrations", response_model=schemas.ApiIntegrationResponse)
async def create_integration(
    req: schemas.ApiIntegrationCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """특정 서비스의 API 키를 입력받아 암호화한 후 DB에 업서트(Upsert)합니다."""
    item = await crud.upsert_user_api_key(db, user_id, req.service_name, req.api_key)
    
    # 프론트엔드로 반환할 마스킹 데이터 구성
    prefix = req.api_key[:3] if len(req.api_key) > 3 else "key"
    masked = f"sk-{prefix}********"
    
    return schemas.ApiIntegrationResponse(
        id=item.id,
        service_name=item.service_name,
        masked_key=masked,
        created_at=item.created_at,
        updated_at=item.updated_at
    )

@app.get("/api/v1/google/test-integration/debug")
async def debug_google_key(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """현재 연동된 Google API 키를 복호화해서 문자열 형식과 길이를 디버그 출력합니다."""
    integrations = await crud.get_user_api_integrations(db, user_id)
    google_item = next((item for item in integrations if item.service_name == "google"), None)
    if not google_item:
        return {"status": "not_found", "message": "Google Integration이 존재하지 않습니다."}
        
    from app.config import decrypt_token
    try:
        decrypted = decrypt_token(google_item.encrypted_api_key)
        return {
            "status": "found",
            "key_length": len(decrypted),
            "key_starts_with": decrypted[:10],
            "key_ends_with": decrypted[-10:] if len(decrypted) > 10 else "",
            "is_json": decrypted.startswith("{") and decrypted.endswith("}")
        }
    except Exception as e:
        return {"status": "error", "message": f"복호화 실패: {str(e)}"}

@app.post("/api/v1/google/test-integration")
async def test_google_integration(
    user_id: uuid.UUID = Depends(get_current_user_id)
):
    """구글 캘린더에 테스트 일정을 등록하고, Gmail을 통해 테스트 메일을 나 자신에게 발송합니다."""
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    start_time = (now + datetime.timedelta(hours=1)).isoformat()
    end_time = (now + datetime.timedelta(hours=2)).isoformat()
    
    calendar_res = await google_workspace.Calendar(
        user_id=user_id,
        summary="AI 비서 연동 테스트 일정",
        start_time=start_time,
        end_time=end_time
    )
    
    gmail_res = await google_workspace.send_test_email(
        user_id=user_id,
        to_email="me",
        subject="AI 비서 연동 테스트 메일",
        body="이 메일은 AI 비서 연동을 검증하기 위해 전송된 테스트 메일입니다."
    )
    
    return {
        "calendar_test": calendar_res,
        "gmail_test": gmail_res
    }

@app.get("/api/v1/google/login")
async def google_login(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """구글 로그인 승인 주소로 사용자를 리다이렉트합니다."""
    # 유저의 google_client_id 가져오기
    integrations = await crud.get_user_api_integrations(db, user_id)
    client_id_item = next((item for item in integrations if item.service_name == "google_client_id"), None)
    if not client_id_item:
        raise HTTPException(
            status_code=400,
            detail="Google Client ID가 먼저 등록되어야 합니다. 환경설정에서 입력해 주세요."
        )
        
    from app.config import decrypt_token
    try:
        client_id = decrypt_token(client_id_item.encrypted_api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Client ID 복호화 실패: {str(e)}")
        
    # Google OAuth 인증 URL 구성
    import urllib.parse
    params = {
        "client_id": client_id,
        "redirect_uri": "http://localhost:8000/api/v1/google/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": str(user_id)
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(auth_url)

@app.get("/api/v1/google/callback")
async def google_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """구글 로그인 승인 완료 후 리다이렉트되어 Authorization Code를 수신합니다."""
    try:
        user_id = uuid.UUID(state)
    except ValueError:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("http://localhost:3000?google_auth=error&message=Invalid_state_user_id")

    # DB 또는 Mock에서 Client ID & Secret 가져오기
    integrations = await crud.get_user_api_integrations(db, user_id)
    client_id_item = next((item for item in integrations if item.service_name == "google_client_id"), None)
    client_secret_item = next((item for item in integrations if item.service_name == "google_client_secret"), None)
    
    if not client_id_item or not client_secret_item:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("http://localhost:3000?google_auth=error&message=Missing_client_credentials")

    from app.config import decrypt_token
    try:
        client_id = decrypt_token(client_id_item.encrypted_api_key)
        client_secret = decrypt_token(client_secret_item.encrypted_api_key)
    except Exception as e:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("http://localhost:3000?google_auth=error&message=Key_decryption_failed")

    # 구글 토큰 서버로 Code 교환 요청
    import httpx
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": "http://localhost:8000/api/v1/google/callback",
        "grant_type": "authorization_code"
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(token_url, data=payload)
            if resp.status_code != 200:
                err_body = resp.text
                from fastapi.responses import RedirectResponse
                return RedirectResponse(f"http://localhost:3000?google_auth=error&message=Token_exchange_failed_{resp.status_code}")
                
            token_data = resp.json()
    except Exception as e:
        from fastapi.responses import RedirectResponse
        return RedirectResponse("http://localhost:3000?google_auth=error&message=Token_request_exception")

    # 기존에 저장된 토큰이 있었는지 체크
    existing_google = next((item for item in integrations if item.service_name == "google"), None)
    existing_refresh_token = None
    if existing_google:
        try:
            old_decrypted = decrypt_token(existing_google.encrypted_api_key)
            import json
            old_cred = json.loads(old_decrypted)
            existing_refresh_token = old_cred.get("refresh_token")
        except Exception:
            pass

    # 구글은 prompt=consent가 없을 경우 refresh_token을 주지 않을 수 있으므로 기존 refresh_token을 유지해줍니다.
    refresh_token = token_data.get("refresh_token") or existing_refresh_token

    # Credentials 규격 JSON 구성
    credentials_dict = {
        "token": token_data.get("access_token"),
        "refresh_token": refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": token_data.get("scope", "").split(" ")
    }
    
    # UserApiIntegration에 'google' 서비스명으로 저장
    import json
    await crud.upsert_user_api_key(db, user_id, "google", json.dumps(credentials_dict))

    from fastapi.responses import RedirectResponse
    return RedirectResponse("http://localhost:3000?google_auth=success")



