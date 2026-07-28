from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from core.exceptions import ServiceError
from core.user.entities import AdminUser, RegularUser
from core.user.exceptions import InvalidCredentialsError, InvalidTokenError, UserAlreadyExistsError
from infrastructure.exceptions import UnitOfWorkError
from infrastructure.unit_of_work import UnitOfWork
from user.repositories import UserRepository

ACCESS_TOKEN_EXPIRE_MINUTES = 1
REFRESH_TOKEN_EXPIRE_MINUTES = 10
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"


class UserService:
    def __init__(self, repository: UserRepository, uow: UnitOfWork):
        self.repository = repository
        self.uow = uow

    @classmethod
    def with_session(cls, session):
        return cls(UserRepository(session), UnitOfWork(session))

    def register_user(self, username, password, email, is_admin, permissions):
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

        try:
            with self.uow:
                if self.repository.get_by_username(username):
                    raise UserAlreadyExistsError(username)
                if self.repository.get_by_email(email):
                    raise UserAlreadyExistsError(email)
                self.repository.add(user)
        except UnitOfWorkError as error:
            raise ServiceError("Failed to register user") from error

    def get_all_users(self):
        return self.repository.get_all()

    def get_current_user(self, token):
        username = self.verify_token(token, "access")
        user = self.repository.get_by_username(username)
        if not user:
            raise InvalidTokenError("User not found")
        return user

    @staticmethod
    def verify_password(plain_password, hashed_password):
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

    def authenticate_user(self, username, password):
        user = self.repository.get_by_username(username)
        if not user or not self.verify_password(password, user.password):
            return None
        return user

    def login(self, username, password):
        user = self.authenticate_user(username, password)
        if not user:
            raise InvalidCredentialsError()

        access_token = self.create_token(
            data={"sub": user.username, "type": "access"},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        refresh_token = self.create_token(
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
                raise InvalidTokenError()
            return payload.get("sub")
        except JWTError as error:
            raise InvalidTokenError() from error
