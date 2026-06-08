"""Pydantic schemas for request/response validation."""

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from models import UserRole


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class PaginatedResponse[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
class ShoutrrrPayload(BaseModel):
    """Payload POSTed to /shoutrrr by the shoutrrr client."""

    message: str = Field(..., min_length=1, max_length=65535)
    title: str | None = Field(None, max_length=512)
    # Any extra fields are accepted and stored verbatim as raw_payload
    model_config = {"extra": "allow"}


class NotificationOut(BaseModel):
    id: uuid.UUID
    sender_name: str | None
    title: str | None
    message: str
    received_at: datetime
    source_ip: str | None
    # Parsed from raw_payload at serialization time — never stored directly
    custom_fields: dict[str, Any] = {}

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _parse_custom_fields(cls, values: Any) -> Any:
        """Parse raw_payload JSON into custom_fields when building from ORM."""
        # ORM objects expose attributes; dicts come from JSON deserialization
        if hasattr(values, "__dict__"):
            raw = getattr(values, "raw_payload", None)
        else:
            raw = values.get("raw_payload") if isinstance(values, dict) else None
        if raw:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    if isinstance(values, dict):
                        values.setdefault("custom_fields", parsed)
                    else:
                        # For ORM objects, inject via __dict__ manipulation isn't safe;
                        # return a dict representation instead
                        d = {
                            c: getattr(values, c, None)
                            for c in [
                                "id",
                                "sender_name",
                                "title",
                                "message",
                                "received_at",
                                "source_ip",
                                "raw_payload",
                            ]
                        }
                        d["custom_fields"] = parsed
                        return d
            except (json.JSONDecodeError, TypeError):
                pass
        return values


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
class UserOut(BaseModel):
    id: uuid.UUID
    sub: str
    email: str
    username: str
    full_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: str | None = None
    username: str | None = None
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None


class UserCreate(BaseModel):
    sub: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)
    username: str = Field(..., min_length=1, max_length=255)
    full_name: str | None = None
    role: UserRole = UserRole.viewer


# ---------------------------------------------------------------------------
# Access Tokens
# ---------------------------------------------------------------------------
class AccessTokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    user_id: uuid.UUID
    expires_at: datetime | None = None


class AccessTokenOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None
    is_active: bool
    # owner username for display
    owner_username: str | None = None

    model_config = {"from_attributes": True}


class AccessTokenCreated(AccessTokenOut):
    """Includes the raw token – only returned once at creation time."""

    raw_token: str = ""


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------
class PluginOut(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    config: dict[str, Any]

    model_config = {"from_attributes": True}


class PluginUpdate(BaseModel):
    enabled: bool | None = None
    config: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class OIDCCallbackResponse(BaseModel):
    session_token: str
    user: UserOut
