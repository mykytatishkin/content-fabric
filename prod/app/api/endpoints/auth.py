"""Authentication endpoints — login, register, me, 2FA."""

from __future__ import annotations

import secrets
import uuid

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_current_user
from app.core.audit import log as audit_log
from app.core.security import create_access_token, hash_password, verify_password
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    TotpDisableRequest,
    TotpSetupResponse,
    TotpVerifyRequest,
    UserResponse,
)
from shared.db.repositories import user_repo

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


# ── Login / Register ────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
@_limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest):
    user = user_repo.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # 2FA check
    if user.get("totp_enabled"):
        if not body.totp_code:
            return TokenResponse(access_token="", requires_2fa=True)
        if not _verify_totp(user, body.totp_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA code")

    user_repo.update_last_login(user["id"])
    token = create_access_token({"sub": user["id"]})
    audit_log("login", actor_id=user["id"], entity_type="user", entity_id=user["id"])
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@_limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest):
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
    audit_log("register", actor_id=user_id, entity_type="user", entity_id=user_id)
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
        totp_enabled=user.get("totp_enabled", False),
    )


# ── 2FA (TOTP) ─────────────────────────────────────────────────────


@router.post("/2fa/setup", response_model=TotpSetupResponse)
async def setup_2fa(user: dict = Depends(get_current_user)):
    """Generate a TOTP secret. User must call /2fa/verify to activate."""
    if user.get("totp_enabled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="2FA already enabled")

    secret = pyotp.random_base32()
    user_repo.set_totp_secret(user["id"], secret)

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user["email"], issuer_name="Content Fabric")

    backup_codes = [secrets.token_hex(6) for _ in range(8)]

    audit_log("2fa.setup_initiated", actor_id=user["id"], entity_type="user", entity_id=user["id"])
    return TotpSetupResponse(secret=secret, provisioning_uri=uri, backup_codes=backup_codes)


@router.post("/2fa/verify")
async def verify_2fa(body: TotpVerifyRequest, user: dict = Depends(get_current_user)):
    """Confirm TOTP setup with a valid code. Activates 2FA."""
    secret = user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call /2fa/setup first")
    if user.get("totp_enabled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="2FA already enabled")

    totp = pyotp.TOTP(secret)
    if not totp.verify(body.code, valid_window=1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")

    backup_codes = [secrets.token_hex(6) for _ in range(8)]
    user_repo.enable_totp(user["id"], backup_codes)

    audit_log("2fa.enabled", actor_id=user["id"], entity_type="user", entity_id=user["id"])
    return {"ok": True, "backup_codes": backup_codes}


@router.post("/2fa/disable")
async def disable_2fa(body: TotpDisableRequest, user: dict = Depends(get_current_user)):
    """Disable 2FA. Requires password confirmation."""
    if not user.get("totp_enabled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA not enabled")
    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    user_repo.disable_totp(user["id"])
    audit_log("2fa.disabled", actor_id=user["id"], entity_type="user", entity_id=user["id"])
    return {"ok": True}


# ── Helpers ─────────────────────────────────────────────────────────


def _verify_totp(user: dict, code: str) -> bool:
    """Check TOTP code or backup code."""
    secret = user.get("totp_secret")
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    if totp.verify(code, valid_window=1):
        return True
    # Try backup codes
    return user_repo.consume_backup_code(user["id"], code)
