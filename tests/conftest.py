from datetime import timedelta

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.permissions import Permission
from core.user.services import ACCESS_TOKEN_EXPIRE_MINUTES, UserService
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
def create_user(db_session):
    async def factory(
        username="test_user",
        email="test@example.com",
        password="secret",
        is_admin=False,
        permissions: list[Permission] | None = None,
    ):
        user = User(
            username=username,
            email=email,
            password=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            is_admin=is_admin,
            permissions=[permission.value for permission in permissions or []],
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return factory


@pytest.fixture
def auth_headers():
    def factory(user):
        token = UserService.create_token(
            data={"sub": user.username, "type": "access"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {"Authorization": token}

    return factory
