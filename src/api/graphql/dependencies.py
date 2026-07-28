from fastapi import Depends
from fastapi.security import APIKeyHeader

from api.dependencies import get_user_service
from core.user.exceptions import InvalidTokenError
from core.user.services import UserService


async def get_current_user(
    token: str = Depends(APIKeyHeader(name="Authorization", auto_error=False)),
    service: UserService = Depends(get_user_service),
):
    if not token:
        return None
    try:
        return await service.get_current_user(token)
    except InvalidTokenError:
        return None


async def get_context(
    current_user=Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    return {"current_user": current_user, "user_service": user_service}
