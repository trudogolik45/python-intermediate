from datetime import datetime

from pydantic import BaseModel, ConfigDict

from core.permissions import Permission


class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    is_admin: bool = False
    permissions: list[Permission] | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class PatchUser(BaseModel):
    is_admin: bool


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    email: str
    created_at: datetime
    updated_at: datetime
