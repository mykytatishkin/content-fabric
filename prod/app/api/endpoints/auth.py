"""Authentication endpoints — login, register, me, 2FA, password reset, email verify."""

import logging
import os
import secrets
import uuid

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import get_current_user
from app.core.audit import log as audit_log
from app.core.security import create_access_token, hash_password, verify_password
from app.core.tokens import (
    PASSWORD_RESET_TTL_SEC,
    VERIFICATION_TOKEN_TTL_SEC,
    is_token_ts_expired,
    make_reset_token,
    make_verification_token,
    parse_token_ts,
)

logger = logging.getLogger(__name__)
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
    TotpDisableRequest,
    TotpSetupResponse,
    TotpVerifyRequest,
    UserResponse,
    VerifyEmailRequest,
)
from shared.db.models import UserStatus
from shared.db.repositories import user_repo
from shared.notifications import email as email_sender

router = APIRouter()
_limiter = Limiter(key_func=get_remote_address)


# ── Login / Register ────────────────────────────────────────────────


@router.post("/login", response_model=TokenResponse)
@_limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest):
    user = user_repo.get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        logger.warning("Login failed: email=%s ip=%s", body.email, request.client.host if request.client else "unknown")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # Email-verification gate (Yii: User::STATUS_INACTIVE blocks login)
    if int(user.get("status") or 0) == int(UserStatus.INACTIVE):
        logger.info("Login blocked — email not verified: user=%s", user["id"])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Check your inbox or request a new link.",
        )

    # 2FA check
    if user.get("totp_enabled"):
        if not body.totp_code:
            logger.info("Login requires 2FA: user=%s", user["id"])
            return TokenResponse(access_token="", requires_2fa=True)
        if not _verify_totp(user, body.totp_code):
            logger.warning("Login 2FA failed: user=%s ip=%s", user["id"], request.client.host if request.client else "unknown")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA code")

    user_repo.update_last_login(user["id"])
    token = create_access_token({"sub": user["id"]})
    audit_log("login", actor_id=user["id"], entity_type="user", entity_id=user["id"])
    logger.info("Login success: user=%s email=%s", user["id"], body.email)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@_limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest):
    if user_repo.get_user_by_email(body.email):
        logger.warning("Registration conflict: email=%s already exists", body.email)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    if user_repo.get_user_by_username(body.username):
        logger.warning("Registration conflict: username=%s already exists", body.username)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user_id = user_repo.create_user(
        uuid=str(uuid.uuid4()),
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        auth_key=secrets.token_hex(16),
        display_name=body.display_name,
    )

    # Optional email verification gate (Yii: actionSignup → sendEmail).
    require_verification = os.environ.get("EMAIL_VERIFICATION_REQUIRED", "").lower() in (
        "1", "true", "yes", "on",
    )
    if require_verification:
        verification_token = make_verification_token()
        user_repo.set_verification_token(user_id, verification_token)
        user_repo.set_status(user_id, int(UserStatus.INACTIVE))
        verify_url = f"{_public_base_url()}/app/verify-email/{verification_token}"
        try:
            email_sender.send_verification_email(
                to=body.email,
                verify_url=verify_url,
                user_name=body.display_name or body.username,
            )
        except Exception:
            logger.exception("Failed to send verification email to %s", body.email)
        audit_log("register", actor_id=user_id, entity_type="user", entity_id=user_id)
        logger.info(
            "Registration success (pending verification): user=%s email=%s",
            user_id, body.email,
        )
        # No access token: user must verify first.
        return TokenResponse(access_token="", requires_2fa=False)

    token = create_access_token({"sub": user_id})
    audit_log("register", actor_id=user_id, entity_type="user", entity_id=user_id)
    logger.info("Registration success: user=%s username=%s email=%s", user_id, body.username, body.email)
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
@_limiter.limit("5/minute")
async def setup_2fa(request: Request, user: dict = Depends(get_current_user)):
    """Generate a TOTP secret. User must call /2fa/verify to activate."""
    if user.get("totp_enabled"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="2FA already enabled")

    secret = pyotp.random_base32()
    user_repo.set_totp_secret(user["id"], secret)

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user["email"], issuer_name="Content Fabric")

    backup_codes = [secrets.token_hex(6) for _ in range(8)]

    audit_log("2fa.setup_initiated", actor_id=user["id"], entity_type="user", entity_id=user["id"])
    logger.info("2FA setup initiated: user=%s", user["id"])
    return TotpSetupResponse(secret=secret, provisioning_uri=uri, backup_codes=backup_codes)


@router.post("/2fa/verify")
@_limiter.limit("5/minute")
async def verify_2fa(request: Request, body: TotpVerifyRequest, user: dict = Depends(get_current_user)):
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
@_limiter.limit("5/minute")
async def disable_2fa(request: Request, body: TotpDisableRequest, user: dict = Depends(get_current_user)):
    """Disable 2FA. Requires password confirmation."""
    if not user.get("totp_enabled"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA not enabled")
    if not verify_password(body.password, user["password_hash"]):
        logger.warning("2FA disable failed — wrong password: user=%s", user["id"])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    user_repo.disable_totp(user["id"])
    audit_log("2fa.disabled", actor_id=user["id"], entity_type="user", entity_id=user["id"])
    logger.info("2FA disabled: user=%s", user["id"])
    return {"ok": True}


# ── Password reset & email verification ────────────────────────────
#
# Mirrors Yii frontend:
#   SiteController::actionRequestPasswordReset    (lines 172-188)
#   SiteController::actionResetPassword           (lines 197-214)
#   SiteController::actionVerifyEmail             (lines 223-237)
#   SiteController::actionResendVerificationEmail (lines 244-258)
#   common/models/User::generatePasswordResetToken / generateEmailVerificationToken
#   common/config/params.php — passwordResetTokenExpire = 3600


def _public_base_url() -> str:
    """Return the canonical scheme://host that goes into emailed links."""
    base = os.environ.get("APP_BASE_URL", "").rstrip("/")
    return base or "http://127.0.0.1:8000"


@router.post("/forgot-password")
@_limiter.limit("5/minute")
async def forgot_password(request: Request, body: ForgotPasswordRequest):
    """Issue a password-reset link. Returns the same response regardless of
    whether the email exists — to avoid leaking which addresses are registered."""
    generic_ok = {
        "ok": True,
        "message": "If an account exists, an email has been sent.",
    }
    user = user_repo.get_user_by_email(body.email)
    if not user:
        logger.info("Forgot-password: no user for email=%s", body.email)
        return generic_ok

    if int(user.get("status") or 0) != int(UserStatus.ACTIVE):
        logger.info(
            "Forgot-password: skipping non-active user id=%s status=%s",
            user["id"], user.get("status"),
        )
        return generic_ok

    token = make_reset_token()
    user_repo.set_password_reset_token(user["id"], token)
    reset_url = f"{_public_base_url()}/app/reset-password/{token}"
    sent = email_sender.send_password_reset_email(
        to=user["email"],
        reset_url=reset_url,
        user_name=user.get("display_name") or user.get("username"),
    )
    audit_log(
        "password_reset.requested",
        actor_id=user["id"], entity_type="user", entity_id=user["id"],
    )
    logger.info(
        "Password reset requested for user=%s email_sent=%s",
        user["id"], sent,
    )
    return generic_ok


@router.post("/reset-password")
@_limiter.limit("5/minute")
async def reset_password(request: Request, body: ResetPasswordRequest):
    """Apply a new password using a single-use reset token."""
    if not body.token or parse_token_ts(body.token) is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if is_token_ts_expired(body.token, PASSWORD_RESET_TTL_SEC):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = user_repo.get_user_by_reset_token(body.token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user_repo.change_password(user["id"], hash_password(body.password))
    user_repo.set_password_reset_token(user["id"], None)
    audit_log(
        "password_reset.completed",
        actor_id=user["id"], entity_type="user", entity_id=user["id"],
    )
    logger.info("Password reset completed for user=%s", user["id"])
    return {"ok": True}


def _do_verify_email(token: str) -> dict:
    """Shared verify-email logic used by both POST body and GET path endpoints.

    Mirrors Yii frontend SiteController::actionVerifyEmail (lines 223-258).
    """
    if not token or parse_token_ts(token) is None:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    if is_token_ts_expired(token, VERIFICATION_TOKEN_TTL_SEC):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = user_repo.get_user_by_verification_token(token)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    # Idempotent reject: only INACTIVE users may consume the token.
    if int(user.get("status") or 0) != int(UserStatus.INACTIVE):
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user_repo.mark_email_verified(user["id"])
    audit_log(
        "email.verified",
        actor_id=user["id"], entity_type="user", entity_id=user["id"],
    )
    logger.info("Email verified for user=%s", user["id"])
    return {"ok": True}


@router.post("/verify-email")
@_limiter.limit("5/minute")
async def verify_email(request: Request, body: VerifyEmailRequest):
    """Mark email confirmed: status INACTIVE → ACTIVE, clear verification_token."""
    return _do_verify_email(body.token)


@router.get("/verify-email/{token}")
@_limiter.limit("5/minute")
async def verify_email_by_path(request: Request, token: str):
    """GET variant: token is in URL path. Mirrors Yii's actionVerifyEmail signature."""
    return _do_verify_email(token)


@router.post("/resend-verification")
@_limiter.limit("5/minute")
async def resend_verification(request: Request, body: ResendVerificationRequest):
    """Re-issue a verification token + email for an INACTIVE user.

    Always returns the same generic response to avoid enumeration.
    """
    generic_ok = {
        "ok": True,
        "message": "If an account exists, an email has been sent.",
    }
    user = user_repo.get_user_by_email(body.email)
    if not user:
        logger.info("Resend-verification: no user for email=%s", body.email)
        return generic_ok
    if int(user.get("status") or 0) != int(UserStatus.INACTIVE):
        logger.info(
            "Resend-verification: user id=%s already verified (status=%s)",
            user["id"], user.get("status"),
        )
        return generic_ok

    token = make_verification_token()
    user_repo.set_verification_token(user["id"], token)
    verify_url = f"{_public_base_url()}/app/verify-email/{token}"
    sent = email_sender.send_verification_email(
        to=user["email"],
        verify_url=verify_url,
        user_name=user.get("display_name") or user.get("username"),
    )
    audit_log(
        "email.verification_resent",
        actor_id=user["id"], entity_type="user", entity_id=user["id"],
    )
    logger.info(
        "Verification resent for user=%s email_sent=%s", user["id"], sent,
    )
    return generic_ok


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
