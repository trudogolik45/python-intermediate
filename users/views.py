from typing import List, Optional

from fastapi import APIRouter, Query

from users.managers import user_manager
from users.models import AdminUser, RegularUser, PERMISSIONS

user_router = APIRouter(prefix="/users", tags=["users"])

@user_router.post("")
def add_user(username: str, email: str, is_admin: bool, permissions: Optional[List[str]] = Query(
    default=None,
    title="Permissions",
    example=PERMISSIONS,
    enum=PERMISSIONS
)):
    if is_admin:
        user = AdminUser(username=username, email=email)
    else:
        user = RegularUser(username=username, email=email, permissions=permissions)

    user_manager.add_user(user)
    return {"message": f"User {username} added successfully."}

@user_router.get("")
def get_all_users():
    return user_manager.get_all_users()