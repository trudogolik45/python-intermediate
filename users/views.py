from datetime import timedelta
from typing import List, Optional

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Query

from users.managers import user_manager
from users.models import AdminUser, RegularUser, PERMISSIONS
from users.services import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    UserService,
)

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

    user_manager.add_user(user)
    return {"message": f"User {username} added successfully."}


@user_router.get("")
def get_all_users():
    return user_manager.get_all_users()


@user_router.get("/login")
def login(username: str, password: str):
    user = UserService.authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)

    access_token = UserService.create_token(
        data={"sub": user.username, "type": "access"}, expires_delta=access_token_expires
    )
    refresh_token = UserService.create_token(
        data={"sub": user.username, "type": "refresh"}, expires_delta=refresh_token_expires
    )
    return {"access_token": access_token, "refresh_token": refresh_token}


@user_router.get("/refresh")
def refresh_token(token: str):
    username = UserService.verify_token(token, "refresh")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = UserService.create_token(
        data={"sub": username, "type": "access"}, expires_delta=access_token_expires
    )
    return {"access_token": access_token}


@user_router.get("/me")
def me(current_user=Depends(UserService.get_current_user)):
    return {"message": f"Hello, {current_user.username}!"}
