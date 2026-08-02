from fastapi import APIRouter, Depends

from api.dependencies import get_user_service
from api.rest.user.decorators import handle_users_errors, require_permissions
from api.rest.user.dependencies import get_current_user
from api.rest.user.models import CurrentUser, PatchUser, UserCreate, UserLogin
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


@user_router.patch("/{user_id}")
@require_permissions(Permission.UPDATE_USER)
@handle_users_errors
async def patch_user(
    user_id: int,
    payload: PatchUser,
    current_user=Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    user = await service.patch_user(user_id, payload.is_admin)
    return user.get_info()


@user_router.post("/login")
@handle_users_errors
async def login(payload: UserLogin, service: UserService = Depends(get_user_service)):
    return await service.login(payload.username, payload.password)


@user_router.get("/refresh")
@handle_users_errors
async def refresh_token(token: str, service: UserService = Depends(get_user_service)):
    return service.refresh_access_token(token)


@user_router.get("/me", response_model=CurrentUser)
async def me(current_user=Depends(get_current_user)):
    return current_user
