"""Authentication endpoints — login, register, me."""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from shared.db.repositories import user_repo

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    user = user_repo.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user_repo.update_last_login(user["id"])
    token = create_access_token({"sub": user["id"]})
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    if user_repo.get_user_by_email(body.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if user_repo.get_user_by_username(body.username):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user_id = user_repo.create_user(
        uuid=str(uuid.uuid4()),
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        auth_key=secrets.token_hex(16),
        display_name=body.display_name,
    )
    token = create_access_token({"sub": user_id})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return UserResponse(
        id=user["id"],
        uuid=user["uuid"],
        username=user["username"],
        email=user["email"],
        display_name=user.get("display_name"),
        avatar_url=user.get("avatar_url"),
        timezone=user.get("timezone"),
    )
