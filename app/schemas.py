import uuid
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# === User Schemas ===
class UserCreate(BaseModel):
    email: str = Field(..., example="user@argos.security")

class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    
    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    profile_data: Dict[str, Any] = Field(..., example={"name": "홍길동", "role": "관리자"})

# === AI Chat Schemas ===
class ChatRequest(BaseModel):
    query: str = Field(..., example="오늘 내 구글 캘린더 일정이 뭐야?")

class ChatResponse(BaseModel):
    response: str
    tts_response: str
    function_called: bool

# === Google Workspace Schemas ===
class CalendarEventCreate(BaseModel):
    summary: str = Field(..., example="팀 주간 미팅")
    start_time: str = Field(..., example="2026-06-24T14:00:00+09:00")
    end_time: str = Field(..., example="2026-06-24T15:00:00+09:00")

class SpreadsheetAppendRequest(BaseModel):
    spreadsheet_id: str
    row_data: List[Any]

class DriveSearchRequest(BaseModel):
    keyword: str

# === IoT Schemas ===
class IoTControlRequest(BaseModel):
    device_id: str = Field(..., example="plug_main_overload")
    target_status: str = Field(..., example="ON")  # ON, OFF

class IoTControlResponse(BaseModel):
    device_id: str
    name: str
    type: str
    status: str
    current_power_w: float
    message: str

# === Orchestration Schemas ===
class OrchestrationRequest(BaseModel):
    scenario_name: str = Field(..., example="send_report_email")
    user_approval: Optional[str] = Field(None, example="진행해")

class OrchestrationResponse(BaseModel):
    state_id: str
    scenario: str
    status: str
    message: str

# === Consultation Schemas ===
class ConsultationRequest(BaseModel):
    raw_text: str = Field(..., example="오늘 스마트홈 제어 이상 전력에 대해 분석하고 DTW 성문 임계치를 조정하기로 합의함.")

# === API Integration Settings Schemas ===
class ApiIntegrationCreate(BaseModel):
    service_name: str = Field(..., example="switchbot")
    api_key: str = Field(..., example="sb_secret_token_12345")

class ApiIntegrationResponse(BaseModel):
    id: uuid.UUID
    service_name: str
    masked_key: str
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True

