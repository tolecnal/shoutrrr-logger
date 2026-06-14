import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserRole(enum.StrEnum):
    viewer = "viewer"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # unique=True + index=True together produce a single unique index (ix_users_sub)
    sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    access_tokens: Mapped[list["AccessToken"]] = relationship(
        "AccessToken", back_populates="user", cascade="all, delete-orphan"
    )


class AccessToken(Base):
    __tablename__ = "access_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Stored as a bcrypt hash; the raw token is only shown once at creation
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Optional expiration – NULL means unlimited
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # True  → admin-managed, visible to all users in the notification feed
    # False → private, visible only to the owning user
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Per-token override for the ingestion rate limit (notifications/minute).
    # NULL  → inherit the global "rate_limit_per_minute" setting
    # 0     → explicitly unlimited
    # >0    → custom per-minute limit
    rate_limit_override: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ---- External delivery policy (per-token) --------------------------------
    # Whether notifications ingested with this token may leave the application
    # through each external delivery channel. The token's creator decides; all
    # default to True (opt-out). Each flag is evaluated once, at ingestion time.
    # To add a new channel: add a column here, gate it at its dispatch site, and
    # expose it in EXTERNAL_DELIVERY_CHANNELS below + the token dialogs.
    #
    # allow_plugin_dispatch: forward to plugins (Slack/Splunk/webhook → 3rd parties)
    allow_plugin_dispatch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    # allow_email_alerts: send matched-alert emails. The in-app GUI alert is
    # always created regardless — this only suppresses the outbound email.
    allow_email_alerts: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    user: Mapped["User"] = relationship("User", back_populates="access_tokens")

    __table_args__ = (
        # token_hash is a deterministic SHA-256 digest, so bearer-token auth can
        # do a direct indexed lookup instead of scanning every active token.
        Index("ix_access_tokens_token_hash", "token_hash", unique=True),
        Index("ix_access_tokens_user_global", "user_id", "is_global"),
    )


# Single source of truth for the per-token external delivery toggles, consumed
# by the token schemas, services, and frontend (via /api/v1/... metadata). Add a
# new channel here (plus its AccessToken column and dispatch-site gate) and it
# flows through create/update/out automatically.
#
#   field: the AccessToken column / schema field name
#   label/description: shown in the token dialogs
EXTERNAL_DELIVERY_CHANNELS: tuple[dict[str, str], ...] = (
    {
        "field": "allow_plugin_dispatch",
        "label": "Allow plugins",
        "description": (
            "Let plugins (Slack, Splunk, webhooks, …) forward notifications "
            "sent with this token to third-party services."
        ),
    },
    {
        "field": "allow_email_alerts",
        "label": "Allow email alerts",
        "description": (
            "Let matching alert rules email notifications sent with this token. "
            "In-app alerts are unaffected."
        ),
    },
)

EXTERNAL_DELIVERY_FIELDS: tuple[str, ...] = tuple(c["field"] for c in EXTERNAL_DELIVERY_CHANNELS)


class MonitoringToken(Base):
    """Tokens intended purely for external monitoring systems like Nagios or Icinga2."""

    __tablename__ = "monitoring_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (Index("ix_monitoring_tokens_token_hash", "token_hash", unique=True),)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The access token used to deliver this notification (nullable – token may be deleted later)
    token_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("access_tokens.id", ondelete="SET NULL"), nullable=True
    )
    # Resolved at ingest time so log entries survive token deletion
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="info")
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_notifications_received_at", "received_at"),
        Index("ix_notifications_token_received", "token_id", "received_at"),
        Index("ix_notifications_token_last_received", "token_id", "last_received_at"),
        Index(
            "ix_notifications_message_gin",
            "message",
            postgresql_using="gin",
            postgresql_ops={"message": "gin_trgm_ops"},
        ),
        Index(
            "ix_notifications_title_gin",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_notifications_sender_name_gin",
            "sender_name",
            postgresql_using="gin",
            postgresql_ops={"sender_name": "gin_trgm_ops"},
        ),
    )


class PluginConfig(Base):
    """Plugin-level settings for a global plugin (one row per plugin).

    The per-configuration state (enabled/config/rules) lives in named
    PluginProfile rows; this table only holds settings that apply to the
    plugin as a whole.
    """

    __tablename__ = "plugin_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # == plugin_id
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    allow_user_configs: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class PluginProfile(Base):
    """One named global configuration profile of a plugin (admin-managed).

    Mirrors UserPluginConfig: every enabled profile is dispatched
    independently with its own config and routing rules. Admins may create
    any number of profiles.
    """

    __tablename__ = "plugin_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Default", server_default="Default"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Free-form JSON config merged on top of the plugin's default_config
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rules: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (Index("ix_plugin_profiles_plugin_name", "plugin_id", "name", unique=True),)


class RoutingRule(Base):
    """Reusable routing rule for plugins."""

    __tablename__ = "routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # NULL user_id means it's a global rule
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    severities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    tokens: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    custom_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class UserPluginConfig(Base):
    """One named configuration profile of a plugin for a specific user.

    A user may have multiple profiles per plugin (e.g. several Slack
    channels), each with its own config and routing rules; every enabled
    profile is dispatched independently. The number of profiles per plugin
    is capped by the "user_plugin_profiles_max" setting (admins exempt).
    """

    __tablename__ = "user_plugin_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, default="Default", server_default="Default"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rules: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (
        Index(
            "ix_user_plugin_configs_user_plugin_name", "user_id", "plugin_id", "name", unique=True
        ),
    )


class AppSetting(Base):
    """Admin-configurable application settings stored as JSON values."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Stored as JSONB so ints, booleans, and strings are all native
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class ApiMetricLog(Base):
    """One row per API request: method, route template, status, and latency."""

    __tablename__ = "api_metric_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Route template, e.g. /api/v1/notifications/{notification_id}
    path: Mapped[str] = mapped_column(String(256), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index("ix_api_metric_logs_created_at", "created_at"),
        Index("ix_api_metric_logs_path", "path"),
    )


class AuditLog(Base):
    """Records admin actions: who did what, to which resource, and when."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable + denormalized username so log entries survive user deletion
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # e.g. "user.create", "token.update", "settings.update"
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
    )


class AlertRule(Base):
    """User-defined rules that trigger alerts when a matching notification arrives."""

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # "exact", "contains", "regex"
    match_type: Mapped[str] = mapped_column(String(32), nullable=False, default="contains")
    # The string or regex to match
    match_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    # "title", "message", "all"
    match_target: Mapped[str] = mapped_column(String(32), nullable=False, default="all")
    # "global_only", "personal_only", "all"
    notification_scope: Mapped[str] = mapped_column(String(32), nullable=False, default="all")

    send_email: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


class UserAlert(Base):
    """An alert triggered for a specific user based on an AlertRule match."""

    __tablename__ = "user_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    notification_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True
    )
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    notification: Mapped["Notification"] = relationship(lazy="noload")
    rule: Mapped["AlertRule"] = relationship(lazy="noload")
    user: Mapped["User"] = relationship(lazy="noload")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index("ix_user_alerts_created_at", "created_at"),
        Index("ix_user_alerts_user_id_is_read", "user_id", "is_read"),
    )


class PluginUsageDaily(Base):
    """Daily aggregated usage statistics for plugin dispatch operations."""

    __tablename__ = "plugin_usage_daily"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # The date bucket (usually stored with time 00:00:00)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    plugin_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # Global profiles won't have a user_id, user profiles will
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    # The specific profile UUID (could be PluginProfile or UserPluginConfig)
    profile_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index(
            "ix_plugin_usage_daily_unique",
            "date",
            "plugin_id",
            "profile_id",
            "user_id",
            unique=True,
        ),
    )
