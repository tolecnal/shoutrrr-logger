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

    user: Mapped["User"] = relationship("User", back_populates="access_tokens")

    __table_args__ = (
        # token_hash is a deterministic SHA-256 digest, so bearer-token auth can
        # do a direct indexed lookup instead of scanning every active token.
        Index("ix_access_tokens_token_hash", "token_hash", unique=True),
        Index("ix_access_tokens_user_global", "user_id", "is_global"),
    )


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
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    source_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_notifications_received_at", "received_at"),
        Index("ix_notifications_token_received", "token_id", "received_at"),
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
    """Persists the enabled state and config dict for each plugin."""

    __tablename__ = "plugin_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # == plugin_id
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Free-form JSON config merged on top of the plugin's default_config
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
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
