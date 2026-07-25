from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from users.managers import user_manager
from users.permissions import Permission
from users.services import UserService


def get_current_user(token: str = Depends(APIKeyHeader(name="Authorization"))):
    username = UserService.verify_token(token, "access")
    user = user_manager.get_user(username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def check_permissions(*required: Permission):
    def dependency(current_user=Depends(get_current_user)):
        if not all(permission in current_user.permissions for permission in required):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
        return current_user

    return dependency
