import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from cryptography.fernet import Fernet

class Settings(BaseSettings):
    # 데이터베이스 설정
    # PostgreSQL의 asyncpg 드라이버를 사용하므로, postgresql+asyncpg:// 형태로 변환하여 사용하도록 래퍼를 구성합니다.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/argos"
    
    # Gemini API 설정
    GEMINI_API_KEY: str = "YOUR_GEMINI_API_KEY"
    
    # 보안 및 암호화 설정 (OAuth 토큰 저장 시 사용)
    # Fernet 키는 32바이트 urlsafe base64로 인코딩된 키여야 합니다.
    # 없으면 새로 생성하도록 초기화합니다.
    ENCRYPTION_KEY: str = ""
    
    # 포트 및 호스트 설정
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Google API OAuth2 클라이언트 설정 (개발 및 연동 테스트용)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/google/callback"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

# 암호화 키 유효성 확인 및 초기화
if not settings.ENCRYPTION_KEY:
    # 키가 없을 경우 메모리 상에 임시 키를 생성하여 동작하도록 합니다.
    # 운영 환경에서는 반드시 고정된 ENCRYPTION_KEY를 .env에 설정해야 합니다.
    settings.ENCRYPTION_KEY = Fernet.generate_key().decode()

fernet = Fernet(settings.ENCRYPTION_KEY.encode())

def encrypt_token(token: str) -> str:
    """토큰을 암호화하여 반환합니다."""
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """암호화된 토큰을 복호화하여 반환합니다."""
    return fernet.decrypt(encrypted_token.encode()).decode()
