from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from users.dependencies import get_current_user
from users.permissions import Permission
from users.services import UserService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post("")
async def add_user(
    username: str,
    password: str,
    email: str,
    is_admin: bool,
    permissions: Optional[List[Permission]] = Query(default=None, title="Permissions"),
):
    UserService.register_user(username, password, email, is_admin, permissions)
    return {"message": f"User {username} added successfully."}


@user_router.get("")
async def get_all_users():
    return UserService.get_all_users()


@user_router.get("/login")
async def login(username: str, password: str):
    return UserService.login(username, password)


@user_router.get("/refresh")
async def refresh_token(token: str):
    return UserService.refresh_access_token(token)


@user_router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {"message": f"Hello, {current_user.username}!"}
