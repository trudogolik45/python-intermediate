from fastapi import Depends
from fastapi.security import APIKeyHeader

from users.managers import user_manager
from users.services import UserService


def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization"))):
    username = UserService.verify_token(token, "access")
    return user_manager.users.get(username)
