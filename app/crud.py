import uuid
import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app import models

# === DB 오프라인 환경을 대비한 인메모리 백업 모의 데이터스페이스 ===
_MOCK_USERS: Dict[uuid.UUID, models.User] = {}
_MOCK_PROFILES: Dict[uuid.UUID, models.UserProfile] = {}
_MOCK_MEMORIES: List[models.SemanticMemory] = []
_MOCK_SIGNATURES: Dict[uuid.UUID, models.VoiceSignature] = {}
_MOCK_ORCHESTRATIONS: Dict[uuid.UUID, models.OrchestrationState] = {}
_MOCK_NOTIFICATIONS: List[models.SystemNotification] = []
_MOCK_CREDENTIALS: Dict[uuid.UUID, models.GoogleCredential] = {}

_MOCK_INTEGRATIONS: List[models.UserApiIntegration] = []

# === User CRUD ===
async def get_user(db: AsyncSession, user_id: uuid.UUID) -> Optional[models.User]:
    try:
        stmt = select(models.User).where(models.User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        print(f"[CRUD Fallback] get_user using mock: {e}")
        return _MOCK_USERS.get(user_id)

async def create_user(db: AsyncSession, email: str) -> models.User:
    new_user = models.User(id=uuid.uuid4(), email=email, created_at=datetime.datetime.utcnow())
    try:
        db.add(new_user)
        await db.flush()
        profile = models.UserProfile(user_id=new_user.id, profile_data={})
        db.add(profile)
        await db.flush()
        # 성공 시 로컬에도 동기화
        _MOCK_USERS[new_user.id] = new_user
        _MOCK_PROFILES[new_user.id] = profile
        return new_user
    except Exception as e:
        print(f"[CRUD Fallback] create_user using mock: {e}")
        profile = models.UserProfile(user_id=new_user.id, profile_data={})
        _MOCK_USERS[new_user.id] = new_user
        _MOCK_PROFILES[new_user.id] = profile
        return new_user

# === User Profile CRUD ===
async def get_user_profile(db: AsyncSession, user_id: uuid.UUID) -> Optional[models.UserProfile]:
    try:
        stmt = select(models.UserProfile).where(models.UserProfile.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        print(f"[CRUD Fallback] get_user_profile using mock: {e}")
        if user_id not in _MOCK_PROFILES:
            _MOCK_PROFILES[user_id] = models.UserProfile(user_id=user_id, profile_data={})
        return _MOCK_PROFILES.get(user_id)

async def update_user_profile(db: AsyncSession, user_id: uuid.UUID, profile_data: Dict[str, Any]) -> Optional[models.UserProfile]:
    try:
        profile = await get_user_profile(db, user_id)
        if profile:
            profile.profile_data = profile_data
            db.add(profile)
            await db.flush()
            _MOCK_PROFILES[user_id] = profile
        return profile
    except Exception as e:
        print(f"[CRUD Fallback] update_user_profile using mock: {e}")
        profile = _MOCK_PROFILES.get(user_id)
        if not profile:
            profile = models.UserProfile(user_id=user_id, profile_data=profile_data)
        else:
            profile.profile_data = profile_data
        _MOCK_PROFILES[user_id] = profile
        return profile

# === Semantic Memory CRUD ===
async def save_semantic_memory(db: AsyncSession, user_id: uuid.UUID, query: str, response: str, embedding: List[float]) -> models.SemanticMemory:
    new_memory = models.SemanticMemory(
        id=uuid.uuid4(),
        user_id=user_id,
        query=query,
        response=response,
        embedding=embedding,
        created_at=datetime.datetime.utcnow()
    )
    try:
        db.add(new_memory)
        await db.flush()
        _MOCK_MEMORIES.append(new_memory)
        return new_memory
    except Exception as e:
        print(f"[CRUD Fallback] save_semantic_memory using mock: {e}")
        _MOCK_MEMORIES.append(new_memory)
        return new_memory

async def retrieve_semantic_memories(db: AsyncSession, user_id: uuid.UUID, query_embedding: List[float], limit: int = 3) -> List[models.SemanticMemory]:
    try:
        stmt = (
            select(models.SemanticMemory)
            .where(models.SemanticMemory.user_id == user_id)
            .order_by(models.SemanticMemory.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        print(f"[CRUD Fallback] retrieve_semantic_memories using mock: {e}")
        user_mems = [m for m in _MOCK_MEMORIES if m.user_id == user_id]
        return user_mems[-limit:]

# === Voice Signature CRUD ===
async def get_voice_signature(db: AsyncSession, user_id: uuid.UUID) -> Optional[models.VoiceSignature]:
    try:
        stmt = select(models.VoiceSignature).where(models.VoiceSignature.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        print(f"[CRUD Fallback] get_voice_signature using mock: {e}")
        return _MOCK_SIGNATURES.get(user_id)

async def register_voice(db: AsyncSession, user_id: uuid.UUID, mfcc_signature: List[List[float]], threshold: float = 100.0) -> models.VoiceSignature:
    try:
        signature = await get_voice_signature(db, user_id)
        if signature:
            signature.mfcc_signature = mfcc_signature
            signature.similarity_threshold = threshold
        else:
            signature = models.VoiceSignature(
                user_id=user_id,
                mfcc_signature=mfcc_signature,
                similarity_threshold=threshold
            )
            db.add(signature)
        await db.flush()
        _MOCK_SIGNATURES[user_id] = signature
        return signature
    except Exception as e:
        print(f"[CRUD Fallback] register_voice using mock: {e}")
        signature = models.VoiceSignature(
            user_id=user_id,
            mfcc_signature=mfcc_signature,
            similarity_threshold=threshold
        )
        _MOCK_SIGNATURES[user_id] = signature
        return signature

async def update_voice_lock_threshold(db: AsyncSession, user_id: uuid.UUID, new_threshold: float) -> Optional[models.VoiceSignature]:
    try:
        signature = await get_voice_signature(db, user_id)
        if signature:
            signature.similarity_threshold = new_threshold
            db.add(signature)
            await db.flush()
            _MOCK_SIGNATURES[user_id] = signature
        return signature
    except Exception as e:
        print(f"[CRUD Fallback] update_voice_lock_threshold using mock: {e}")
        signature = _MOCK_SIGNATURES.get(user_id)
        if signature:
            signature.similarity_threshold = new_threshold
            _MOCK_SIGNATURES[user_id] = signature
        return signature

# === Orchestration State CRUD ===
async def get_orchestration_state(db: AsyncSession, state_id: uuid.UUID) -> Optional[models.OrchestrationState]:
    try:
        stmt = select(models.OrchestrationState).where(models.OrchestrationState.id == state_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        print(f"[CRUD Fallback] get_orchestration_state using mock: {e}")
        return _MOCK_ORCHESTRATIONS.get(state_id)

async def get_pending_orchestration(db: AsyncSession, user_id: uuid.UUID, scenario_name: str) -> Optional[models.OrchestrationState]:
    try:
        stmt = select(models.OrchestrationState).where(
            and_(
                models.OrchestrationState.user_id == user_id,
                models.OrchestrationState.scenario_name == scenario_name,
                models.OrchestrationState.status == "PENDING_APPROVAL"
            )
        ).order_by(models.OrchestrationState.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().first()
    except Exception as e:
        print(f"[CRUD Fallback] get_pending_orchestration using mock: {e}")
        for state in _MOCK_ORCHESTRATIONS.values():
            if state.user_id == user_id and state.scenario_name == scenario_name and state.status == "PENDING_APPROVAL":
                return state
        return None

async def create_orchestration_state(db: AsyncSession, user_id: uuid.UUID, scenario_name: str, status: str, pending_action: Dict[str, Any]) -> models.OrchestrationState:
    state = models.OrchestrationState(
        id=uuid.uuid4(),
        user_id=user_id,
        scenario_name=scenario_name,
        status=status,
        pending_action=pending_action,
        created_at=datetime.datetime.utcnow()
    )
    try:
        db.add(state)
        await db.flush()
        _MOCK_ORCHESTRATIONS[state.id] = state
        return state
    except Exception as e:
        print(f"[CRUD Fallback] create_orchestration_state using mock: {e}")
        _MOCK_ORCHESTRATIONS[state.id] = state
        return state

async def update_orchestration_status(db: AsyncSession, state_id: uuid.UUID, status: str) -> Optional[models.OrchestrationState]:
    try:
        state = await get_orchestration_state(db, state_id)
        if state:
            state.status = status
            db.add(state)
            await db.flush()
            _MOCK_ORCHESTRATIONS[state_id] = state
        return state
    except Exception as e:
        print(f"[CRUD Fallback] update_orchestration_status using mock: {e}")
        state = _MOCK_ORCHESTRATIONS.get(state_id)
        if state:
            state.status = status
            _MOCK_ORCHESTRATIONS[state_id] = state
        return state

# === System Notification CRUD ===
async def create_notification(db: AsyncSession, user_id: uuid.UUID, n_type: str, message: str) -> models.SystemNotification:
    notif = models.SystemNotification(
        id=uuid.uuid4(),
        user_id=user_id,
        type=n_type,
        message=message,
        is_read=False,
        created_at=datetime.datetime.utcnow()
    )
    try:
        db.add(notif)
        await db.flush()
        _MOCK_NOTIFICATIONS.append(notif)
        return notif
    except Exception as e:
        print(f"[CRUD Fallback] create_notification using mock: {e}")
        _MOCK_NOTIFICATIONS.append(notif)
        return notif

async def get_notifications(db: AsyncSession, user_id: uuid.UUID, limit: int = 50) -> List[models.SystemNotification]:
    try:
        stmt = (
            select(models.SystemNotification)
            .where(models.SystemNotification.user_id == user_id)
            .order_by(models.SystemNotification.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        print(f"[CRUD Fallback] get_notifications using mock: {e}")
        user_notifs = [n for n in _MOCK_NOTIFICATIONS if n.user_id == user_id]
        return sorted(user_notifs, key=lambda x: x.created_at, reverse=True)[:limit]

# === Google Credential CRUD ===
async def get_google_credential(db: AsyncSession, user_id: uuid.UUID) -> Optional[models.GoogleCredential]:
    try:
        stmt = select(models.GoogleCredential).where(models.GoogleCredential.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()
    except Exception as e:
        print(f"[CRUD Fallback] get_google_credential using mock: {e}")
        return _MOCK_CREDENTIALS.get(user_id)

async def save_google_credential(db: AsyncSession, user_id: uuid.UUID, credentials_json: Dict[str, Any]) -> models.GoogleCredential:
    try:
        cred = await get_google_credential(db, user_id)
        if cred:
            cred.credentials_json = credentials_json
        else:
            cred = models.GoogleCredential(
                user_id=user_id,
                credentials_json=credentials_json
            )
            db.add(cred)
        await db.flush()
        _MOCK_CREDENTIALS[user_id] = cred
        return cred
    except Exception as e:
        print(f"[CRUD Fallback] save_google_credential using mock: {e}")
        cred = models.GoogleCredential(user_id=user_id, credentials_json=credentials_json)
        _MOCK_CREDENTIALS[user_id] = cred
        return cred



# === UserApiIntegration CRUD ===
async def get_user_api_integrations(db: AsyncSession, user_id: uuid.UUID) -> List[models.UserApiIntegration]:
    try:
        stmt = select(models.UserApiIntegration).where(models.UserApiIntegration.user_id == user_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())
    except Exception as e:
        print(f"[CRUD Fallback] get_user_api_integrations using mock: {e}")
        return [item for item in _MOCK_INTEGRATIONS if item.user_id == user_id]

async def upsert_user_api_key(db: AsyncSession, user_id: uuid.UUID, service_name: str, raw_api_key: str) -> models.UserApiIntegration:
    from app.config import encrypt_token
    encrypted_key = encrypt_token(raw_api_key)
    
    try:
        stmt = select(models.UserApiIntegration).where(
            and_(
                models.UserApiIntegration.user_id == user_id,
                models.UserApiIntegration.service_name == service_name
            )
        )
        result = await db.execute(stmt)
        integration = result.scalar_one_or_none()
        
        if integration:
            integration.encrypted_api_key = encrypted_key
        else:
            integration = models.UserApiIntegration(
                user_id=user_id,
                service_name=service_name,
                encrypted_api_key=encrypted_key
            )
            db.add(integration)
            
        await db.flush()
        # 동기화
        for i, item in enumerate(_MOCK_INTEGRATIONS):
            if item.user_id == user_id and item.service_name == service_name:
                _MOCK_INTEGRATIONS[i] = integration
                break
        else:
            _MOCK_INTEGRATIONS.append(integration)
            
        return integration
    except Exception as e:
        print(f"[CRUD Fallback] upsert_user_api_key using mock: {e}")
        
        # 동기화 탐색
        for i, item in enumerate(_MOCK_INTEGRATIONS):
            if item.user_id == user_id and item.service_name == service_name:
                item.encrypted_api_key = encrypted_key
                return item
                
        mock_item = models.UserApiIntegration(
            id=uuid.uuid4(),
            user_id=user_id,
            service_name=service_name,
            encrypted_api_key=encrypted_key,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        _MOCK_INTEGRATIONS.append(mock_item)
        return mock_item
