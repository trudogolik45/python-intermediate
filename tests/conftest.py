import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from infrastructure.config import settings
from infrastructure.database import Base, get_session
from main import app
from user import models  # noqa: F401 — импорт регистрирует User в Base.metadata

engine = create_async_engine(settings.test_database_url)
TestSessionLocal = async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
async def db_session():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session):
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
