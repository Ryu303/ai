import uuid
import datetime
from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean, Float, JSON, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base

# pgvector가 정상적으로 설치되어 있을 경우 Vector 타입을 임포트합니다.
# 로컬 개발 환경에서 pgvector가 없는 경우를 대비하여 폴백 처리를 지원하도록 설계합니다.
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # pgvector 라이브러리가 없는 경우 Float List를 처리하는 가상 타입으로 대체
    from sqlalchemy.types import UserDefinedType
    class Vector(UserDefinedType):
        def __init__(self, dim):
            self.dim = dim
        def get_col_spec(self, **kw):
            return f"vector({self.dim})"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    memories = relationship("SemanticMemory", back_populates="user", cascade="all, delete-orphan")
    voice_signature = relationship("VoiceSignature", back_populates="user", uselist=False, cascade="all, delete-orphan")
    orchestrations = relationship("OrchestrationState", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("SystemNotification", back_populates="user", cascade="all, delete-orphan")
    credential = relationship("GoogleCredential", back_populates="user", uselist=False, cascade="all, delete-orphan")

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    profile_data = Column(JSONB, default={}, nullable=False)  # 이름, 역할, 성향, System Instruction 병합 데이터 등
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="profile")

class SemanticMemory(Base):
    __tablename__ = "semantic_memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    query = Column(String, nullable=False)
    response = Column(String, nullable=False)
    embedding = Column(Vector(1536), nullable=False)  # gemini-embedding-001 차원수 1536
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="memories")

class VoiceSignature(Base):
    __tablename__ = "voice_signatures"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # 40차원 MFCC 특징 벡터 시퀀스를 JSON 포맷으로 저장
    mfcc_signature = Column(JSONB, nullable=False)
    # Dynamic Time Warping (DTW) 매칭 임계치
    similarity_threshold = Column(Float, default=100.0, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="voice_signature")

class OrchestrationState(Base):
    __tablename__ = "orchestration_states"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    scenario_name = Column(String, nullable=False)
    status = Column(String, default="PENDING_APPROVAL", nullable=False)  # PENDING_APPROVAL, EXECUTING, COMPLETED, FAILED
    # 승인 대기 중인 실제 실행할 태스크/시나리오 목록 및 상태 파라미터 저장
    pending_action = Column(JSONB, default={}, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="orchestrations")

class SystemNotification(Base):
    __tablename__ = "system_notifications"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    type = Column(String, nullable=False)  # CALENDAR_REMINDER, SMART_PLUG_OVERLOAD, HOTSPOT_DETECTED 등
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="notifications")

class GoogleCredential(Base):
    __tablename__ = "google_credentials"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # 암호화된 토큰 정보를 저장하기 위한 JSON
    credentials_json = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="credential")



class UserApiIntegration(Base):
    __tablename__ = "user_api_integrations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    service_name = Column(String, nullable=False)  # 'switchbot', 'google', 'weather' 등
    encrypted_api_key = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User")

