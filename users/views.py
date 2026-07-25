from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from users.dependencies import get_current_user
from users.models import PERMISSIONS
from users.services import UserService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post("")
def add_user(
    username: str,
    password: str,
    email: str,
    is_admin: bool,
    permissions: Optional[List[str]] = Query(
        default=None, title="Permissions", examples=[PERMISSIONS], enum=PERMISSIONS
    ),
):
    UserService.register_user(username, password, email, is_admin, permissions)
    return {"message": f"User {username} added successfully."}


@user_router.get("")
def get_all_users():
    return UserService.get_all_users()


@user_router.get("/login")
def login(username: str, password: str):
    return UserService.login(username, password)


@user_router.get("/refresh")
def refresh_token(token: str):
    return UserService.refresh_access_token(token)


@user_router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {"message": f"Hello, {current_user.username}!"}
