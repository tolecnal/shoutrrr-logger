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
class CursorPage[T](BaseModel):
    """Keyset/cursor-paginated response, newest first.

    ``total``/``pages`` are informational (for "X total" / "page N of M"
    display); navigation is driven by ``next_cursor`` — pass it back as the
    ``cursor`` query parameter to fetch the next page. ``next_cursor`` is
    ``None`` on the last page.
    """

    items: list[T]
    total: int
    page_size: int
    pages: int
    next_cursor: str | None = None


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
    severity: str
    tags: list[str]
    fingerprint: str | None
    occurrences: int
    state: str
    received_at: datetime
    last_received_at: datetime
    source_ip: str | None
    # Parsed from raw_payload at serialization time — never stored directly
    custom_fields: dict[str, Any] = {}
    # Whether the requesting user may delete this notification. Populated by
    # the list endpoint (admins: always; viewers: only their own non-global
    # token's notifications). Defaults False elsewhere (export/get/state),
    # where it is not used.
    can_delete: bool = False

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
                                "severity",
                                "tags",
                                "fingerprint",
                                "occurrences",
                                "state",
                                "received_at",
                                "last_received_at",
                                "source_ip",
                                "raw_payload",
                            ]
                        }
                        d["custom_fields"] = parsed
                        return d
            except (json.JSONDecodeError, TypeError):
                pass
        return values


class NotificationSearchFilters(BaseModel):
    senders: list[str]
    tags: list[str]
    severities: list[str]


class NotificationStateUpdate(BaseModel):
    state: str = Field(..., pattern="^(new|acknowledged|resolved)$")


class NotificationDeleteRequest(BaseModel):
    """Explicit selection of notification IDs to delete (Gmail-style)."""

    # Capped to bound the IN (...) clause and the audit payload.
    ids: list[uuid.UUID] = Field(..., min_length=1, max_length=500)


class NotificationDeleteResult(BaseModel):
    requested: int
    deleted: int


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
    # When None the creating admin's user_id is used automatically
    user_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    is_global: bool = True
    # Per-token rate limit override (notifications/minute). None = inherit the
    # global "rate_limit_per_minute" setting; 0 = unlimited; >0 = custom limit.
    rate_limit_override: int | None = Field(None, ge=0)
    # External delivery policy (see models.EXTERNAL_DELIVERY_CHANNELS).
    allow_plugin_dispatch: bool = True
    allow_email_alerts: bool = True


class AccessTokenUpdate(BaseModel):
    """Partial token update; omitted fields are left unchanged."""

    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None
    # New override value (notifications/minute); see AccessTokenCreate.
    rate_limit_override: int | None = Field(None, ge=0)
    # When true, resets rate_limit_override to "inherit the global setting".
    clear_rate_limit_override: bool = False
    # External delivery policy; None leaves the flag unchanged.
    allow_plugin_dispatch: bool | None = None
    allow_email_alerts: bool | None = None


class PersonalTokenCreate(BaseModel):
    """Payload for a user creating their own private token."""

    name: str = Field(..., min_length=1, max_length=255)
    expires_at: datetime | None = None
    allow_plugin_dispatch: bool = True
    allow_email_alerts: bool = True


class PersonalTokenUpdate(BaseModel):
    """Partial private-token update; omitted fields are left unchanged."""

    name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None
    allow_plugin_dispatch: bool | None = None
    allow_email_alerts: bool | None = None


class AccessTokenOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    name: str
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None
    is_active: bool
    is_global: bool = True
    # owner username for display
    owner_username: str | None = None
    # None = inherit the global "rate_limit_per_minute" setting; 0 = unlimited
    rate_limit_override: int | None = None
    # External delivery policy (see models.EXTERNAL_DELIVERY_CHANNELS).
    allow_plugin_dispatch: bool = True
    allow_email_alerts: bool = True

    model_config = {"from_attributes": True}


class AccessTokenCreated(AccessTokenOut):
    """Includes the raw token – only returned once at creation time."""

    raw_token: str = ""


class MonitoringTokenCreate(BaseModel):
    name: str = Field(..., max_length=255)


class MonitoringTokenUpdate(BaseModel):
    name: str | None = Field(None, max_length=255)
    is_active: bool | None = None


class MonitoringTokenOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class MonitoringTokenCreated(MonitoringTokenOut):
    """Includes the raw token – only returned once at creation time."""

    raw_token: str = ""


# ---------------------------------------------------------------------------
# Routing Rules
# ---------------------------------------------------------------------------
class RoutingRuleBase(BaseModel):
    name: str
    severities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tokens: list[str] = Field(default_factory=list)
    custom_fields: dict[str, str] = Field(default_factory=dict)


class RoutingRuleCreate(RoutingRuleBase):
    pass


class RoutingRuleUpdate(BaseModel):
    name: str | None = None
    severities: list[str] | None = None
    tags: list[str] | None = None
    tokens: list[str] | None = None
    custom_fields: dict[str, str] | None = None


class RoutingRuleOut(RoutingRuleBase):
    id: uuid.UUID
    user_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Plugins
# ---------------------------------------------------------------------------
class PluginProfileOut(BaseModel):
    """One named configuration profile of a plugin (global or per-user)."""

    id: uuid.UUID
    name: str
    enabled: bool
    config: dict[str, Any]
    rules: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PluginOut(BaseModel):
    """A registered plugin with its global (admin-managed) profiles."""

    id: str
    name: str
    description: str
    enabled: bool
    allow_user_configs: bool
    profiles: list[PluginProfileOut] = Field(default_factory=list)
    active_global_profiles: int = 0
    active_user_profiles: int = 0


class PluginUpdate(BaseModel):
    """Plugin-level settings; per-configuration state lives on profiles."""

    enabled: bool | None = None
    allow_user_configs: bool | None = None


class UserPluginOut(BaseModel):
    """A plugin available for user configuration, with all of the user's profiles."""

    plugin_id: str
    name: str = ""
    description: str = ""
    profiles: list[PluginProfileOut] = Field(default_factory=list)
    # Resolved cap for this user (0 = unlimited); the UI disables "add
    # profile" when len(profiles) >= max_profiles and max_profiles != 0.
    max_profiles: int = 0


class PluginProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # Optionally seed the new profile by copying an existing one
    # ("duplicate profile"); config/rules below win over the copied values.
    copy_from: uuid.UUID | None = None
    config: dict[str, Any] | None = None
    rules: list[dict[str, Any]] | None = None


class PluginProfileUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    enabled: bool | None = None
    config: dict[str, Any] | None = None
    rules: list[dict[str, Any]] | None = None


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class SettingOut(BaseModel):
    key: str
    value: Any
    label: str
    description: str
    default: Any
    min_value: Any = None
    max_value: Any = None
    unit: str = ""
    value_type: str = "int"


class SettingsUpdate(BaseModel):
    values: dict[str, Any]


class SmtpTestRequest(BaseModel):
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    smtp_from_address: str


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------
class DayStat(BaseModel):
    date: str  # YYYY-MM-DD
    count: int


class SenderStat(BaseModel):
    sender: str | None
    count: int


class NotificationStats(BaseModel):
    total: int
    today: int
    this_week: int
    by_day: list[DayStat]
    top_senders: list[SenderStat]


# ---------------------------------------------------------------------------
# API Performance
# ---------------------------------------------------------------------------
class EndpointStat(BaseModel):
    path: str
    method: str
    request_count: int
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    error_count: int
    error_rate: float


class RequestTimeSeries(BaseModel):
    time: str  # ISO datetime (truncated to hour)
    count: int
    avg_ms: float


class ApiPerformanceStats(BaseModel):
    total_requests: int
    avg_ms: float
    p95_ms: float
    error_rate: float
    by_endpoint: list[EndpointStat]
    by_hour: list[RequestTimeSeries]
    window_hours: int


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------
class AuditLogOut(BaseModel):
    id: uuid.UUID
    actor_user_id: uuid.UUID | None
    actor_username: str | None
    action: str
    target_type: str
    target_id: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class OIDCCallbackResponse(BaseModel):
    session_token: str
    user: UserOut


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
class AlertRuleBase(BaseModel):
    # No CR/LF: name flows into the alert email's Subject header.
    name: str = Field(..., min_length=1, max_length=255, pattern=r"^[^\r\n]+$")
    match_type: str = Field(default="contains", pattern="^(exact|contains|regex)$")
    match_pattern: str = Field(default="", min_length=0)
    match_target: str = Field(default="all", pattern="^(title|message|all)$")
    notification_scope: str = Field(default="all", pattern="^(global_only|personal_only|all)$")
    send_email: bool = False


class AlertRuleCreate(AlertRuleBase):
    pass


class AlertRuleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255, pattern=r"^[^\r\n]+$")
    match_type: str | None = Field(None, pattern="^(exact|contains|regex)$")
    match_pattern: str | None = None
    match_target: str | None = Field(None, pattern="^(title|message|all)$")
    notification_scope: str | None = Field(None, pattern="^(global_only|personal_only|all)$")
    send_email: bool | None = None


class AlertRuleOut(AlertRuleBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserAlertOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    notification_id: uuid.UUID
    rule_id: uuid.UUID | None
    is_read: bool
    created_at: datetime

    notification: NotificationOut | None = None

    model_config = {"from_attributes": True}


class AlertTestRequest(AlertRuleBase):
    notification_id: uuid.UUID | None = None


class AlertTestResult(BaseModel):
    matched_notifications: list[NotificationOut]
    total_matches: int = 0


class TemplatePreviewRequest(BaseModel):
    template: str
    notification_id: uuid.UUID | None = None


class TemplatePreviewResponse(BaseModel):
    html: str
