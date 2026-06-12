"""Business logic for plugin configuration and test dispatch."""

import datetime
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import PluginConfig, User, UserPluginConfig, UserRole
from plugins import registry as plugin_registry
from repositories.plugin_configs import PluginConfigRepository, plugin_config_repository
from repositories.user_plugin_configs import (
    UserPluginConfigRepository,
    user_plugin_config_repository,
)
from schemas import (
    PluginOut,
    PluginUpdate,
    UserPluginOut,
    UserPluginProfileCreate,
    UserPluginProfileOut,
    UserPluginProfileUpdate,
)
from services.settings import settings_service


class PluginService:
    def __init__(
        self,
        repo: PluginConfigRepository = plugin_config_repository,
        user_repo: UserPluginConfigRepository = user_plugin_config_repository,
    ) -> None:
        self._repo = repo
        self._user_repo = user_repo

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
                session,
                PluginConfig(
                    id=plugin_id, enabled=False, allow_user_configs=True, config={}, rules=[]
                ),
            )
        return row

    def _to_out(self, plugin_id: str, row: PluginConfig) -> PluginOut:
        plugin = plugin_registry.get_plugin(plugin_id)
        return PluginOut(
            id=plugin.plugin_id,
            name=plugin.name,
            description=plugin.description,
            enabled=row.enabled,
            allow_user_configs=row.allow_user_configs,
            config=self.merge_config(plugin_id, row),
            rules=row.rules,
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
        if body.allow_user_configs is not None:
            row.allow_user_configs = body.allow_user_configs
        if body.config is not None:
            # Store only the keys that differ from defaults to keep the DB lean
            row.config = body.config
        if body.rules is not None:
            row.rules = body.rules

        await session.commit()
        await session.refresh(row)
        return self._to_out(plugin_id, row)

    # -----------------------------------------------------------------------
    # User Plugins — named configuration profiles
    # -----------------------------------------------------------------------
    async def _resolve_profile_cap(self, session: AsyncSession, user: User) -> int:
        """Max profiles per plugin for this user. 0 = unlimited (admins always)."""
        if user.role == UserRole.admin:
            return 0
        return await settings_service.get_int(session, "user_plugin_profiles_max")

    async def _require_user_configurable(
        self, session: AsyncSession, plugin_id: str
    ) -> PluginConfig:
        plugin = plugin_registry.get_plugin(plugin_id)
        if not plugin:
            raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
        global_row = await self.get_or_create_config(session, plugin_id)
        if not global_row.allow_user_configs:
            raise HTTPException(status_code=403, detail="Plugin not enabled for user configuration")
        return global_row

    async def _get_profile_or_404(
        self, session: AsyncSession, user_id: uuid.UUID, plugin_id: str, profile_id: uuid.UUID
    ) -> UserPluginConfig:
        row = await self._user_repo.get_by_id(session, user_id, profile_id)
        if row is None or row.plugin_id != plugin_id:
            raise HTTPException(status_code=404, detail="Profile not found")
        return row

    def _to_profile_out(self, plugin_id: str, row: UserPluginConfig) -> UserPluginProfileOut:
        plugin = plugin_registry.get_plugin(plugin_id)
        defaults = plugin.default_config if plugin else {}
        return UserPluginProfileOut(
            id=row.id,
            name=row.name,
            enabled=row.enabled,
            config={**defaults, **row.config},
            rules=row.rules,
        )

    async def _to_user_out(
        self, session: AsyncSession, user: User, plugin_id: str
    ) -> UserPluginOut:
        plugin = plugin_registry.get_plugin(plugin_id)
        rows = await self._user_repo.list_by_plugin(session, user.id, plugin_id)
        if not rows:
            # Every plugin always has at least a "Default" profile so the UI
            # has something to edit (mirrors the pre-profile behavior).
            rows = [
                await self._user_repo.add(
                    session,
                    UserPluginConfig(
                        user_id=user.id,
                        plugin_id=plugin_id,
                        name="Default",
                        enabled=False,
                        config={},
                        rules=[],
                    ),
                )
            ]
        return UserPluginOut(
            plugin_id=plugin_id,
            name=plugin.name if plugin else plugin_id,
            description=plugin.description if plugin else "",
            profiles=[self._to_profile_out(plugin_id, r) for r in rows],
            max_profiles=await self._resolve_profile_cap(session, user),
        )

    async def list_user_plugins(self, session: AsyncSession, user: User) -> list[UserPluginOut]:
        result = []
        for plugin in plugin_registry.all_plugins():
            global_row = await self.get_or_create_config(session, plugin.plugin_id)
            if not global_row.allow_user_configs:
                continue
            result.append(await self._to_user_out(session, user, plugin.plugin_id))
        return result

    async def get_user_plugin(
        self, session: AsyncSession, user: User, plugin_id: str
    ) -> UserPluginOut:
        await self._require_user_configurable(session, plugin_id)
        return await self._to_user_out(session, user, plugin_id)

    async def create_user_profile(
        self, session: AsyncSession, user: User, plugin_id: str, body: UserPluginProfileCreate
    ) -> UserPluginProfileOut:
        await self._require_user_configurable(session, plugin_id)

        cap = await self._resolve_profile_cap(session, user)
        if cap > 0:
            count = await self._user_repo.count_by_plugin(session, user.id, plugin_id)
            if count >= cap:
                raise HTTPException(
                    status_code=403,
                    detail=f"Profile limit reached: max {cap} profiles per plugin. "
                    "Ask an administrator to raise the limit.",
                )

        name = body.name.strip()
        if await self._user_repo.get_by_name(session, user.id, plugin_id, name):
            raise HTTPException(status_code=409, detail=f"A profile named '{name}' already exists")

        config: dict[str, Any] = {}
        rules: list[dict[str, Any]] = []
        if body.copy_from is not None:
            source = await self._get_profile_or_404(session, user.id, plugin_id, body.copy_from)
            config = dict(source.config)
            rules = list(source.rules)
        if body.config is not None:
            config = body.config
        if body.rules is not None:
            rules = body.rules

        row = await self._user_repo.add(
            session,
            UserPluginConfig(
                user_id=user.id,
                plugin_id=plugin_id,
                name=name,
                enabled=False,
                config=config,
                rules=rules,
            ),
        )
        return self._to_profile_out(plugin_id, row)

    async def update_user_profile(
        self,
        session: AsyncSession,
        user: User,
        plugin_id: str,
        profile_id: uuid.UUID,
        body: UserPluginProfileUpdate,
    ) -> UserPluginProfileOut:
        await self._require_user_configurable(session, plugin_id)
        row = await self._get_profile_or_404(session, user.id, plugin_id, profile_id)

        if body.name is not None:
            name = body.name.strip()
            if name != row.name:
                if await self._user_repo.get_by_name(session, user.id, plugin_id, name):
                    raise HTTPException(
                        status_code=409, detail=f"A profile named '{name}' already exists"
                    )
                row.name = name
        if body.enabled is not None:
            row.enabled = body.enabled
        if body.config is not None:
            row.config = body.config
        if body.rules is not None:
            row.rules = body.rules

        await session.flush()
        return self._to_profile_out(plugin_id, row)

    async def delete_user_profile(
        self, session: AsyncSession, user: User, plugin_id: str, profile_id: uuid.UUID
    ) -> UserPluginConfig:
        row = await self._get_profile_or_404(session, user.id, plugin_id, profile_id)
        await self._user_repo.delete(session, row)
        return row

    async def test_user_profile(
        self, session: AsyncSession, user: User, plugin_id: str, profile_id: uuid.UUID
    ) -> None:
        """Fire a synthetic test notification through one of the user's profiles.

        Unlike the admin test endpoint this does not require the profile to be
        enabled — testing a configuration before switching it on is the point.
        """
        await self._require_user_configurable(session, plugin_id)
        row = await self._get_profile_or_404(session, user.id, plugin_id, profile_id)
        plugin = plugin_registry.get_plugin(plugin_id)
        config = {**plugin.default_config, **row.config}

        test_notification = {
            "id": str(uuid.uuid4()),
            "sender_name": "shoutrrr-logger test",
            "title": f"Profile test: {row.name}",
            "message": "This is a test notification for your plugin profile.",
            "received_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "source_ip": "127.0.0.1",
            "custom_fields": {},
        }
        try:
            await plugin.on_notification(test_notification, config)
        except Exception as exc:
            detail = str(exc) or repr(exc) or type(exc).__name__
            raise HTTPException(status_code=502, detail=f"Plugin error: {detail}") from exc

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
