from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text
from core.config import config
from core.models import Base

engine = create_async_engine(config.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Добавляем новые колонки если их ещё нет (для существующих БД без миграций)
        for sql in [
            "ALTER TABLE users ADD COLUMN digest_hour INTEGER",
            "ALTER TABLE users ADD COLUMN digest_minute INTEGER",
        ]:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass  # Колонка уже существует


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
