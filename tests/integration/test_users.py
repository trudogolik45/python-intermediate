from http import HTTPStatus


async def test_register_user(client, read_user):
    response = await client.post(
        "/v1/api/users",
        json={"username": "test_user", "password": "secret", "email": "test@example.com"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"message": "User test_user added successfully."}
    assert await read_user("test_user") is not None


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

    response = await client.get("/v1/api/users", headers=await auth_headers(admin))

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert len(body) == 1
    assert body[0]["username"] == "admin"
    assert body[0]["email"] == "admin@example.com"
    assert body[0]["is_admin"] is True


async def test_get_all_users_without_permission(client, create_user, auth_headers):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.get("/v1/api/users", headers=await auth_headers(user))

    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.json()["detail"] == "Not enough permissions"


async def test_get_all_users_without_token(client):
    response = await client.get("/v1/api/users")

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_me(client, create_user, auth_headers):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.get("/v1/api/users/me", headers=await auth_headers(user))

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


async def test_patch_user_grants_admin(client, create_user, auth_headers, read_user):
    target = await create_user(username="target", email="target@example.com")
    admin = await create_user(username="admin", email="admin@example.com", is_admin=True)

    response = await client.patch(
        f"/v1/api/users/{target.id}",
        json={"is_admin": True},
        headers=await auth_headers(admin),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["is_admin"] is True

    stored = await read_user("target")
    assert stored.is_admin is True


async def test_patch_user_revokes_admin(client, create_user, auth_headers, read_user):
    target = await create_user(username="target", email="target@example.com", is_admin=True)
    admin = await create_user(username="admin", email="admin@example.com", is_admin=True)

    response = await client.patch(
        f"/v1/api/users/{target.id}",
        json={"is_admin": False},
        headers=await auth_headers(admin),
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["is_admin"] is False

    stored = await read_user("target")
    assert stored.is_admin is False


async def test_patch_user_without_permission(client, create_user, auth_headers, read_user):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.patch(
        f"/v1/api/users/{user.id}",
        json={"is_admin": True},
        headers=await auth_headers(user),
    )

    assert response.status_code == HTTPStatus.FORBIDDEN

    stored = await read_user("regular")
    assert stored.is_admin is False


async def test_patch_user_without_token(client, create_user):
    user = await create_user(username="regular", email="regular@example.com")

    response = await client.patch(f"/v1/api/users/{user.id}", json={"is_admin": True})

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_patch_unknown_user(client, create_user, auth_headers):
    admin = await create_user(username="admin", email="admin@example.com", is_admin=True)

    response = await client.patch("/v1/api/users/999", json={"is_admin": True}, headers=await auth_headers(admin))

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "User 999 not found"
