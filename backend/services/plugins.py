"""Business logic for plugin configuration and test dispatch."""

import datetime
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import PluginConfig
from plugins import registry as plugin_registry
from repositories.plugin_configs import PluginConfigRepository, plugin_config_repository
from schemas import PluginOut, PluginUpdate


class PluginService:
    def __init__(self, repo: PluginConfigRepository = plugin_config_repository) -> None:
        self._repo = repo

    def merge_config(self, plugin_id: str, row: PluginConfig) -> dict[str, Any]:
        """Merge a plugin's default_config with the stored overrides."""
        plugin = plugin_registry.get_plugin(plugin_id)
        defaults = plugin.default_config if plugin else {}
        return {**defaults, **row.config}

    async def get_or_create_config(self, session: AsyncSession, plugin_id: str) -> PluginConfig:
        """Return the DB row for a plugin, creating it with defaults if absent."""
        row = await self._repo.get_by_id(session, plugin_id)
        if row is None:
            plugin = plugin_registry.get_plugin(plugin_id)
            if plugin is None:
                raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
            row = await self._repo.add(
                session, PluginConfig(id=plugin_id, enabled=False, config={})
            )
        return row

    def _to_out(self, plugin_id: str, row: PluginConfig) -> PluginOut:
        plugin = plugin_registry.get_plugin(plugin_id)
        return PluginOut(
            id=plugin.plugin_id,
            name=plugin.name,
            description=plugin.description,
            enabled=row.enabled,
            config=self.merge_config(plugin_id, row),
        )

    async def list_plugins(self, session: AsyncSession) -> list[PluginOut]:
        result = []
        for plugin in plugin_registry.all_plugins():
            row = await self.get_or_create_config(session, plugin.plugin_id)
            await session.commit()
            result.append(self._to_out(plugin.plugin_id, row))
        return result

    async def get_plugin(self, session: AsyncSession, plugin_id: str) -> PluginOut:
        plugin = plugin_registry.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
        row = await self.get_or_create_config(session, plugin_id)
        await session.commit()
        return self._to_out(plugin_id, row)

    async def update_plugin(
        self, session: AsyncSession, plugin_id: str, body: PluginUpdate
    ) -> PluginOut:
        plugin = plugin_registry.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
        row = await self.get_or_create_config(session, plugin_id)

        if body.enabled is not None:
            row.enabled = body.enabled
        if body.config is not None:
            # Store only the keys that differ from defaults to keep the DB lean
            row.config = body.config

        await session.commit()
        await session.refresh(row)
        return self._to_out(plugin_id, row)

    async def test_plugin(self, session: AsyncSession, plugin_id: str) -> None:
        """Fire a synthetic test notification through the plugin."""
        plugin = plugin_registry.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
        row = await self.get_or_create_config(session, plugin_id)
        if not row.enabled:
            raise HTTPException(status_code=400, detail="Plugin is disabled")
        config = self.merge_config(plugin_id, row)

        test_notification = {
            "id": str(uuid.uuid4()),
            "sender_name": "shoutrrr-logger test",
            "title": "Plugin test",
            "message": "This is a test notification sent from the shoutrrr-logger admin panel.",
            "received_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "source_ip": "127.0.0.1",
            "custom_fields": {},
        }
        try:
            await plugin.on_notification(test_notification, config)
        except Exception as exc:
            # str(exc) can be empty for low-level network errors; fall back to repr
            detail = str(exc) or repr(exc) or type(exc).__name__
            raise HTTPException(status_code=502, detail=f"Plugin error: {detail}") from exc


plugin_service = PluginService()
