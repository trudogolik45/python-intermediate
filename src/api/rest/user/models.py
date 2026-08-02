from pydantic import BaseModel

from core.permissions import Permission


class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    is_admin: bool = False
    permissions: list[Permission] | None = None
