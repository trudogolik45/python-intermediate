from fastapi import Depends
from fastapi.security import APIKeyHeader

from api.dependencies import get_user_service
from api.rest.user.decorators import handle_users_errors
from core.user.services import UserService


@handle_users_errors
async def get_current_user(
    token: str = Depends(APIKeyHeader(name="Authorization")),
    service: UserService = Depends(get_user_service),
):
    return service.get_current_user(token)
