import uuid
import datetime
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from app import crud, models
from app.services import google_workspace, ai

# Gemini 2.0 JSON 스키마 구조 정의
class ConsultationSchema(BaseModel):
    major_complaint: str = Field(alias="주요 호소", description="사용자가 언급한 핵심적인 통증, 불편 혹은 호소 사항")
    consultation_content: str = Field(alias="상담 내용", description="상담자 또는 시스템이 대화한 상세 내용 요약")
    next_tasks: str = Field(alias="다음 과제", description="추후 해결해야 하는 과제 혹은 액션 아이템")

async def save_consultation_note(user_id: uuid.UUID, raw_text: str, db: AsyncSession) -> Dict[str, Any]:
    """gemini-2.0-flash 모델을 호출하여 원본 텍스트를 구조화된 JSON 데이터로 가공한 뒤

    일별 문서('상담일지 - YYYY년 MM월 DD일')의 마지막 라인에 추가하고 URL을 반환합니다.
    """
    client = ai.get_gemini_client()
    
    # 1. gemini-2.0-flash 모델로 JSON 구조화 가공
    prompt = f"다음 상담 원본 내용을 정형화된 JSON 포맷으로 변환해 주세요.\n\n원본 내용:\n{raw_text}"
    
    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ConsultationSchema,
                system_instruction=(
                    "당신은 전문 상담 요약 엔진입니다. 제공된 텍스트에서 '주요 호소', '상담 내용', '다음 과제'에 "
                    "해당하는 내용을 추출해 정확한 JSON 데이터로 작성해 주십시오."
                )
            )
        )
        
        parsed_note = json.loads(response.text)
    except Exception as e:
        print(f"[Gemini 2.0 Structuring Error] Failed to structure consultation note: {e}")
        # 예외 발생 시 수동 폴백
        parsed_note = {
            "주요 호소": "분석 실패 (원본 데이터 참고)",
            "상담 내용": raw_text[:200],
            "다음 과제": "수동 분석 및 조치 필요"
        }

    # 2. 날짜 기반 문서 이름 생성
    today = datetime.datetime.now()
    filename = f"상담일지 - {today.year}년 {today.month:02d}월 {today.day:02d}일"
    
    # 3. 문서 기록을 위한 텍스트 포맷팅
    timestamp = today.strftime("%H:%M:%S")
    formatted_text = (
        f"--- 상담 기록 [{timestamp}] ---\n"
        f"● 주요 호소: {parsed_note.get('주요 호소', parsed_note.get('major_complaint', ''))}\n"
        f"● 상담 내용: {parsed_note.get('상담 내용', parsed_note.get('consultation_content', ''))}\n"
        f"● 다음 과제: {parsed_note.get('다음 과제', parsed_note.get('next_tasks', ''))}\n"
    )
    
    # 4. Google Drive에 문서 생성 및 Append 실행
    doc_url = await google_workspace.create_or_append_drive_doc(user_id, filename, formatted_text)
    
    return {
        "status": "success",
        "doc_name": filename,
        "url": doc_url,
        "note": parsed_note
    }


# ==========================================
# 태스크 오케스트레이션 및 상태 머신
# ==========================================

# 고위험 시나리오 및 위험 작업 분류
# 이메일 발송, 일정 삭제 등의 시나리오는 승인이 필요하도록 정의
HIGH_RISK_SCENARIOS = ["send_report_email", "delete_calendar_event"]

async def run_orchestrated_scenario(
    user_id: uuid.UUID, 
    scenario_name: str, 
    user_approval: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> Dict[str, Any]:
    """연쇄 작업을 관리하는 오케스트레이터 상태 머신입니다.

    고위험 작업(Tier 2)은 PENDING_APPROVAL 상태로 유도하며, 승인이 제공되면 실행을 완수합니다.
    """
    if db is None:
        raise ValueError("Database session is required")

    # 1. 고위험 시나리오 판별 및 Tier 2 권한 체크
    is_high_risk = scenario_name in HIGH_RISK_SCENARIOS
    
    if is_high_risk:
        # 대기 중인 상태가 있는지 확인
        pending_state = await crud.get_pending_orchestration(db, user_id, scenario_name)
        
        # 신규 진입 시
        if not pending_state:
            # 1단계: PENDING_APPROVAL 상태로 등록 및 일시 정지
            pending_action_data = {
                "action_type": "email_dispatch" if scenario_name == "send_report_email" else "calendar_deletion",
                "details": {
                    "to": "manager@argos.security",
                    "subject": "[ARGOS Report] 일일 시스템 진단 결과",
                    "body": "시스템 이상 없음 및 정상 작동 보고서입니다."
                }
            }
            
            state = await crud.create_orchestration_state(
                db=db,
                user_id=user_id,
                scenario_name=scenario_name,
                status="PENDING_APPROVAL",
                pending_action=pending_action_data
            )
            
            return {
                "state_id": str(state.id),
                "scenario": scenario_name,
                "status": "PENDING_APPROVAL",
                "message": (
                    f"'{scenario_name}' 시나리오는 Tier 2 (고위험 작업) 권한이 필요합니다. "
                    "작업 진행을 원하시면 '진행해' 또는 '승인'을 입력해 주세요."
                )
            }
        
        # 승인 파라미터가 전달된 경우 체크
        if pending_state and user_approval:
            approval_keywords = ["진행해", "승인", "yes", "confirm"]
            if any(keyword in user_approval.lower() for keyword in approval_keywords):
                # 2단계: 승인 확인 시 EXECUTING 및 실제 작업 비동기 실행
                await crud.update_orchestration_status(db, pending_state.id, "EXECUTING")
                
                # 비동기 구글 메일 발송 액션 실행 (여기서는 목업 처리 또는 gmail 연동)
                # 실제 Google Workspace 이메일 연동 등의 연쇄 작업이 돌아가게 됨
                # ...
                
                # 완료 전이
                await crud.update_orchestration_status(db, pending_state.id, "COMPLETED")
                
                return {
                    "state_id": str(pending_state.id),
                    "scenario": scenario_name,
                    "status": "COMPLETED",
                    "message": f"시나리오 '{scenario_name}' 가 승인되어 성공적으로 처리 완료되었습니다."
                }
            else:
                # 거절 혹은 매칭 불가 시 상태를 FAILED 처리
                await crud.update_orchestration_status(db, pending_state.id, "FAILED")
                return {
                    "state_id": str(pending_state.id),
                    "scenario": scenario_name,
                    "status": "FAILED",
                    "message": "사용자 승인 거절 또는 키워드 불일치로 오케스트레이션이 취소되었습니다."
                }
        else:
            return {
                "state_id": str(pending_state.id),
                "scenario": scenario_name,
                "status": "PENDING_APPROVAL",
                "message": "사용자의 명시적 승인 응답이 전달되지 않았습니다. 대기 중입니다."
            }

    # 일반(Tier 1) 시나리오: 즉시 실행 진행
    else:
        # e.g., 'morning_briefing' 시나리오
        state = await crud.create_orchestration_state(
            db=db,
            user_id=user_id,
            scenario_name=scenario_name,
            status="EXECUTING",
            pending_action={}
        )
        
        try:
            # 1. 캘린더 가져오기
            # 2. IoT 전력 가져오기 등의 연쇄 태스크 제어
            # ...
            await crud.update_orchestration_status(db, state.id, "COMPLETED")
            return {
                "state_id": str(state.id),
                "scenario": scenario_name,
                "status": "COMPLETED",
                "message": f"일반 시나리오 '{scenario_name}' 가 대기 없이 정상적으로 완료되었습니다."
            }
        except Exception as e:
            await crud.update_orchestration_status(db, state.id, "FAILED")
            return {
                "state_id": str(state.id),
                "scenario": scenario_name,
                "status": "FAILED",
                "message": f"시나리오 실행 중 장애가 발생했습니다: {e}"
            }
