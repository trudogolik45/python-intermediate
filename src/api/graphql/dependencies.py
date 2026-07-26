from fastapi import Depends
from fastapi.security import APIKeyHeader

from core.user.exceptions import InvalidTokenError
from core.user.services import UserService


async def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization", auto_error=False))):
    if not token:
        return None
    try:
        return UserService.get_current_user(token)
    except InvalidTokenError:
        return None


async def get_context(current_user=Depends(get_current_user)):
    return {"current_user": current_user}
