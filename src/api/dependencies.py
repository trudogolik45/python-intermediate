from fastapi import Depends

from core.user.services import UserService
from infrastructure.database import get_session


async def get_user_service(session=Depends(get_session)):
    return UserService.with_session(session)
