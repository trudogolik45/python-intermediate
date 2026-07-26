from fastapi import Depends
from fastapi.security import APIKeyHeader

from users.decorators import handle_users_errors
from users.exceptions import InvalidTokenError
from users.managers import user_manager
from users.services import UserService


@handle_users_errors
async def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization"))):
    username = UserService.verify_token(token, "access")
    user = user_manager.get_user(username)
    if not user:
        raise InvalidTokenError("User not found")
    return user
