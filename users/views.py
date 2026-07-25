from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from users.decorators import handle_users_errors, require_permissions
from users.dependencies import get_current_user
from users.permissions import Permission
from users.services import UserService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post("")
@handle_users_errors
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
@require_permissions(Permission.VIEW_USER)
async def get_all_users(current_user=Depends(get_current_user)):
    return UserService.get_all_users()


@user_router.get("/login")
@handle_users_errors
async def login(username: str, password: str):
    return UserService.login(username, password)


@user_router.get("/refresh")
@handle_users_errors
async def refresh_token(token: str):
    return UserService.refresh_access_token(token)


@user_router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {"message": f"Hello, {current_user.username}!"}
