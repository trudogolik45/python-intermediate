from fastapi import APIRouter, Depends

from api.dependencies import get_user_service
from api.rest.user.decorators import handle_users_errors, require_permissions
from api.rest.user.dependencies import get_current_user
from api.rest.user.models import UserCreate
from core.permissions import Permission
from core.user.services import UserService

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.post("")
@handle_users_errors
async def add_user(payload: UserCreate, service: UserService = Depends(get_user_service)):
    await service.register_user(
        payload.username,
        payload.password,
        payload.email,
        payload.is_admin,
        payload.permissions,
    )
    return {"message": f"User {payload.username} added successfully."}


@user_router.get("")
@require_permissions(Permission.VIEW_USER)
async def get_all_users(
    current_user=Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    return [user.get_info() for user in await service.get_all_users()]


@user_router.get("/login")
@handle_users_errors
async def login(username: str, password: str, service: UserService = Depends(get_user_service)):
    return await service.login(username, password)


@user_router.get("/refresh")
@handle_users_errors
async def refresh_token(token: str, service: UserService = Depends(get_user_service)):
    return service.refresh_access_token(token)


@user_router.get("/me")
async def me(current_user=Depends(get_current_user)):
    return {"message": f"Hello, {current_user.username}!"}
