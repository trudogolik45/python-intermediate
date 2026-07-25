from datetime import datetime, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt

from users.managers import user_manager

ACCESS_TOKEN_EXPIRE_MINUTES = 1
REFRESH_TOKEN_EXPIRE_MINUTES = 10
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"


class UserService:
    @staticmethod
    def verify_password(plain_password, hashed_password):
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    @classmethod
    def authenticate_user(cls, username, password):
        user = user_manager.users.get(username)
        if not user or not cls.verify_password(password, user.password):
            return None
        return user

    @staticmethod
    def create_token(data, expires_delta):
        payload = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        payload.update({"exp": expire})
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

    @classmethod
    def get_current_user(cls, token: str = Depends(APIKeyHeader(name="Authorization"))):
        username = cls.verify_token(token, "access")
        return user_manager.users.get(username)

    @staticmethod
    def verify_token(token: str, token_type: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            exp = payload.get("exp")
            current_token_type = payload.get("type")
            if (
                current_token_type != token_type
                or not exp
                or datetime.now(timezone.utc) > datetime.fromtimestamp(exp, timezone.utc)
            ):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
            return payload.get("sub")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
