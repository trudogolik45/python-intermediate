import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from infrastructure.base import Base
from infrastructure.config import settings
from infrastructure.database import get_session
from main import app
from user.models import User

engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
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


@pytest.fixture
def create_user(client, read_user):
    """Регистрирует пользователя тем же эндпоинтом, что и приложение: хеширование пароля не дублируется."""

    async def factory(username="test_user", email="test@example.com", password="secret", is_admin=False):
        response = await client.post(
            "/v1/api/users",
            json={"username": username, "password": password, "email": email, "is_admin": is_admin},
        )
        response.raise_for_status()
        user = await read_user(username)
        assert user is not None, f"пользователь {username} не сохранился в БД после регистрации"
        return user

    return factory


@pytest.fixture
def auth_headers(client):
    async def factory(user, password="secret"):
        response = await client.post(
            "/v1/api/users/login",
            json={"username": user.username, "password": password},
        )
        return {"Authorization": response.json()["access_token"]}

    return factory


@pytest.fixture
def read_user():
    """Читает пользователя отдельной сессией: незакоммиченное приложением сюда не попадёт."""

    async def factory(username):
        async with TestSessionLocal() as session:
            result = await session.execute(select(User).where(User.username == username))
            return result.scalars().first()

    return factory
