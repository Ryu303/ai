from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.config import settings

# 비동기 데이터베이스 엔진 생성
# settings.DATABASE_URL이 postgresql://로 시작하는 경우 postgresql+asyncpg://로 보정합니다.
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    db_url,
    echo=False,
    future=True
)

# 비동기 세션 팩토리 생성
async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

IS_DB_ONLINE = True

async def get_db():
    """FastAPI에서 의존성 주입(Dependency Injection)으로 사용할 DB 세션 제너레이터입니다."""
    if not IS_DB_ONLINE:
        async with async_session() as session:
            try:
                yield session
            finally:
                await session.close()
        return

    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
