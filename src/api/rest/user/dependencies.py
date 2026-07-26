from fastapi import Depends
from fastapi.security import APIKeyHeader

from api.rest.user.decorators import handle_users_errors
from core.user.services import UserService


@handle_users_errors
async def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization"))):
    return UserService.get_current_user(token)
