from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from infrastructure.config import settings

engine = create_async_engine(settings.async_database_url)
SessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session():
    async with SessionLocal() as session:
        yield session
