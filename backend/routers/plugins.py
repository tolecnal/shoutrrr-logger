"""
Admin routes for plugin management.

GET  /api/admin/plugins          — list all registered plugins with their DB config
GET  /api/admin/plugins/{id}     — get one plugin
PATCH /api/admin/plugins/{id}    — update enabled flag and/or config dict
POST /api/admin/plugins/{id}/test — trigger a test notification through the plugin
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_from_session
from database import get_db
from models import Notification, PluginConfig, UserRole
from plugins import registry
from schemas import PluginOut, PluginUpdate

router = APIRouter(prefix="/admin/plugins", tags=["plugins"])


def _require_admin(user=Depends(get_current_user_from_session)):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


async def _get_or_create_db_config(
    plugin_id: str, db: AsyncSession
) -> PluginConfig:
    """Return the DB row for a plugin, creating it with defaults if absent."""
    row = await db.get(PluginConfig, plugin_id)
    if row is None:
        plugin = registry.get_plugin(plugin_id)
        if plugin is None:
            raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
        row = PluginConfig(id=plugin_id, enabled=False, config={})
        db.add(row)
        await db.flush()
    return row


def _merge(plugin_id: str, row: PluginConfig) -> dict[str, Any]:
    """Merge plugin default_config with stored overrides."""
    plugin = registry.get_plugin(plugin_id)
    defaults = plugin.default_config if plugin else {}
    return {**defaults, **row.config}


@router.get("/custom-field-keys", response_model=list[str])
async def list_custom_field_keys(
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
    limit: int = 500,
) -> list[str]:
    """
    Return the distinct custom_fields keys seen across recent notifications.
    Used by plugin config UIs (e.g. Splunk field-mapping datalists).
    """
    # Use PostgreSQL's jsonb_object_keys() to enumerate keys from raw_payload.
    # We cast the text column to jsonb and skip rows where the payload is not
    # a JSON object (NULL, plain text messages, arrays, etc.).
    sql = text("""
        SELECT DISTINCT k
        FROM (
            SELECT jsonb_object_keys(raw_payload::jsonb) AS k
            FROM notifications
            WHERE raw_payload IS NOT NULL
              AND raw_payload LIKE '{%'
            LIMIT :limit
        ) sub
        ORDER BY k
    """)
    result = await db.execute(sql, {"limit": limit})
    return [row[0] for row in result.fetchall()]


@router.get("", response_model=list[PluginOut])
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> list[PluginOut]:
    plugins = registry.all_plugins()
    result = []
    for p in plugins:
        row = await _get_or_create_db_config(p.plugin_id, db)
        await db.commit()
        result.append(
            PluginOut(
                id=p.plugin_id,
                name=p.name,
                description=p.description,
                enabled=row.enabled,
                config=_merge(p.plugin_id, row),
            )
        )
    return result


@router.get("/{plugin_id}", response_model=PluginOut)
async def get_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> PluginOut:
    plugin = registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    row = await _get_or_create_db_config(plugin_id, db)
    await db.commit()
    return PluginOut(
        id=plugin.plugin_id,
        name=plugin.name,
        description=plugin.description,
        enabled=row.enabled,
        config=_merge(plugin_id, row),
    )


@router.patch("/{plugin_id}", response_model=PluginOut)
async def update_plugin(
    plugin_id: str,
    body: PluginUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> PluginOut:
    plugin = registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    row = await _get_or_create_db_config(plugin_id, db)

    if body.enabled is not None:
        row.enabled = body.enabled
    if body.config is not None:
        # Store only the keys that differ from defaults to keep the DB lean
        row.config = body.config

    await db.commit()
    await db.refresh(row)
    return PluginOut(
        id=plugin.plugin_id,
        name=plugin.name,
        description=plugin.description,
        enabled=row.enabled,
        config=_merge(plugin_id, row),
    )


@router.post("/{plugin_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> dict:
    """Fire a synthetic test notification through the plugin."""
    import datetime, uuid  # noqa: PLC0415
    plugin = registry.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    row = await _get_or_create_db_config(plugin_id, db)
    if not row.enabled:
        raise HTTPException(status_code=400, detail="Plugin is disabled")
    config = _merge(plugin_id, row)

    test_notification = {
        "id": str(uuid.uuid4()),
        "sender_name": "shoutrrr-logger test",
        "title": "Plugin test",
        "message": "This is a test notification sent from the shoutrrr-logger admin panel.",
        "received_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_ip": "127.0.0.1",
        "custom_fields": {},
    }
    try:
        await plugin.on_notification(test_notification, config)
    except Exception as exc:
        # str(exc) can be empty for low-level network errors; fall back to repr
        detail = str(exc) or repr(exc) or type(exc).__name__
        raise HTTPException(status_code=502, detail=f"Plugin error: {detail}") from exc

    return {"detail": "Test notification sent"}
