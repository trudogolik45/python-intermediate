from sqlalchemy import select

from user.models import User


async def test_register_user(client, db_session):
    response = await client.post(
        "/v1/api/users",
        json={"username": "test_user", "password": "secret", "email": "test@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {"message": "User test_user added successfully."}

    result = await db_session.execute(select(User).where(User.username == "test_user"))
    assert result.scalars().first() is not None
