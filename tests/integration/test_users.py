from http import HTTPStatus

from sqlalchemy import select

from user.models import User


async def test_register_user(client, db_session):
    response = await client.post(
        "/v1/api/users",
        json={"username": "test_user", "password": "secret", "email": "test@example.com"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "User test_user added successfully."}

    result = await db_session.execute(select(User).where(User.username == "test_user"))
    assert result.scalars().first() is not None


async def test_register_user_already_exists(client, create_user):
    await create_user(username="test_user", email="test@example.com")

    response = await client.post(
        "/v1/api/users",
        json={"username": "test_user", "password": "secret", "email": "test@example.com"},
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.json()["detail"] == "User test_user already exists"


async def test_login(client, create_user):
    await create_user(username="test_user", password="secret")

    response = await client.post("/v1/api/users/login", json={"username": "test_user", "password": "secret"})

    assert response.status_code == HTTPStatus.OK
    assert response.json().keys() == {"access_token", "refresh_token"}


async def test_login_wrong_password(client, create_user):
    await create_user(username="test_user", password="secret")

    response = await client.post("/v1/api/users/login", json={"username": "test_user", "password": "wrong"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Invalid username or password"


async def test_login_unknown_user(client):
    response = await client.post("/v1/api/users/login", json={"username": "ghost", "password": "secret"})

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Invalid username or password"


async def test_get_all_users_as_admin(client, create_user, auth_headers):
    admin = await create_user(username="admin", email="admin@example.com", is_admin=True)

    response = await client.get("/v1/api/users", headers=auth_headers(admin))

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["username"] == "admin"
    assert body[0]["email"] == "admin@example.com"
    assert body[0]["is_admin"] is True


async def test_get_all_users_without_permission(client, create_user, auth_headers):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.get("/v1/api/users", headers=auth_headers(user))

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["detail"] == "Not enough permissions"


async def test_get_all_users_without_token(client):
    response = await client.get("/v1/api/users")

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_me(client, create_user, auth_headers):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.get("/v1/api/users/me", headers=auth_headers(user))

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["username"] == "regular"
    assert body["email"] == "regular@example.com"
    assert body["created_at"] is not None
    assert body["updated_at"] is not None
    assert "password" not in body


async def test_me_without_token(client):
    response = await client.get("/v1/api/users/me")

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_patch_user_as_admin(client, db_session, create_user, auth_headers):
    target = await create_user(username="target", email="target@example.com")
    admin = await create_user(username="admin", email="admin@example.com", is_admin=True)

    response = await client.patch(
        f"/v1/api/users/{target.id}",
        json={"is_admin": True},
        headers=auth_headers(admin),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["is_admin"] is True

    await db_session.refresh(target)
    assert target.is_admin is True


async def test_patch_user_without_permission(client, db_session, create_user, auth_headers):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.patch(
        f"/v1/api/users/{user.id}",
        json={"is_admin": True},
        headers=auth_headers(user),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN

    await db_session.refresh(user)
    assert user.is_admin is False


async def test_patch_user_without_token(client, create_user):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.patch(f"/v1/api/users/{user.id}", json={"is_admin": True})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_patch_unknown_user(client, create_user, auth_headers):
    admin = await create_user(username="admin", email="admin@example.com", is_admin=True)

    response = await client.patch("/v1/api/users/999", json={"is_admin": True}, headers=auth_headers(admin))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "User 999 not found"
