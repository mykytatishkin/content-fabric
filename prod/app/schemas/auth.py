"""Auth request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None  # required if 2FA is enabled


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requires_2fa: bool = False


class UserResponse(BaseModel):
    id: int
    uuid: str
    username: str
    email: str
    display_name: str | None = None
    avatar_url: str | None = None
    timezone: str | None = None
    totp_enabled: bool = False


class TotpSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: list[str]


class TotpVerifyRequest(BaseModel):
    code: str


class TotpDisableRequest(BaseModel):
    password: str
