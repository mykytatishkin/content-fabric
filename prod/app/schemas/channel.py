"""Channel schemas for platform_channels and platform_oauth_credentials."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

class OAuthCredential(BaseModel):
    """OAuth credential (platform_oauth_credentials) for dropdown."""

    id: int
    name: str
    description: str | None = None
    enabled: bool = True


class ChannelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    platform_channel_id: str = Field(..., min_length=1, max_length=255)
    console_id: int | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Название не может быть пустым")
        return v.strip()

    @field_validator("platform_channel_id")
    @classmethod
    def platform_channel_id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Channel ID не може бути порожнім")
        return v.strip()


class ChannelCredentials(BaseModel):
    """RPA auth credentials for automated OAuth re-authorization."""

    login_email: str = Field(..., max_length=320)
    login_password: str = Field(..., min_length=1)
    totp_secret: str | None = Field(None, max_length=64)
    backup_codes: list[str] | None = None
    proxy_host: str | None = Field(None, max_length=255)
    proxy_port: int | None = Field(None, ge=1, le=65535)
    proxy_username: str | None = Field(None, max_length=255)
    proxy_password: str | None = Field(None, max_length=255)


class ChannelCreate(ChannelBase):
    """Schema for creating a channel."""

    project_id: int | None = None
    credentials: ChannelCredentials | None = None


class ChannelUpdate(BaseModel):
    """Schema for updating a channel."""

    name: str | None = Field(None, min_length=1, max_length=255)
    platform_channel_id: str | None = Field(None, min_length=1, max_length=255)
    console_id: int | None = None
    enabled: bool | None = None


class Channel(ChannelBase):
    """Channel response schema."""

    id: int
    uuid: str | None = None
    project_id: int | None = None
    has_tokens: bool = False
    token_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
