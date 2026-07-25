from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt

from users.managers import user_manager
from users.models import AdminUser, RegularUser

ACCESS_TOKEN_EXPIRE_MINUTES = 1
REFRESH_TOKEN_EXPIRE_MINUTES = 10
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"


class UserService:
    @staticmethod
    def register_user(username, password, email, is_admin, permissions):
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        if is_admin:
            user = AdminUser(username=username, password=hashed_password, email=email)
        else:
            user = RegularUser(
                username=username,
                password=hashed_password,
                email=email,
                permissions=permissions,
            )
        if not user_manager.add_user(user):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists")

    @staticmethod
    def get_all_users():
        return user_manager.get_all_users()

    @staticmethod
    def verify_password(plain_password, hashed_password):
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    @classmethod
    def authenticate_user(cls, username, password):
        user = user_manager.get_user(username)
        if not user or not cls.verify_password(password, user.password):
            return None
        return user

    @classmethod
    def login(cls, username, password):
        user = cls.authenticate_user(username, password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

        access_token = cls.create_token(
            data={"sub": user.username, "type": "access"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token = cls.create_token(
            data={"sub": user.username, "type": "refresh"},
            expires_delta=timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
        )
        return {"access_token": access_token, "refresh_token": refresh_token}

    @classmethod
    def refresh_access_token(cls, token):
        username = cls.verify_token(token, "refresh")
        access_token = cls.create_token(
            data={"sub": username, "type": "access"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {"access_token": access_token}

    @staticmethod
    def create_token(data, expires_delta):
        payload = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        payload.update({"exp": expire})
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

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
