from fastapi import Depends
from fastapi.security import APIKeyHeader

from api.dependencies import get_user_service
from api.rest.errors import handle_domain_errors
from core.user.services import UserService


@handle_domain_errors
async def get_current_user(
    token: str = Depends(APIKeyHeader(name="Authorization")),
    service: UserService = Depends(get_user_service),
):
    return await service.get_current_user(token)
