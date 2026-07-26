from fastapi import Depends
from fastapi.security import APIKeyHeader

from api.rest.user.decorators import handle_users_errors
from core.user.exceptions import InvalidTokenError
from core.user.services import UserService
from user.managers import user_manager


@handle_users_errors
async def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization"))):
    username = UserService.verify_token(token, "access")
    user = user_manager.get_user(username)
    if not user:
        raise InvalidTokenError("User not found")
    return user
