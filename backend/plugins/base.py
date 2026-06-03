"""
Base class for shoutrrr-logger plugins.

All plugins must subclass BasePlugin and implement:
  - ``plugin_id``  – unique snake_case identifier, e.g. "splunk"
  - ``name``       – human-readable display name
  - ``description``– one-line description shown in the admin UI
  - ``default_config`` – dict with all config keys and their defaults
  - ``on_notification(notification, config)`` – called after every saved notification

See PLUGINS.md for a complete authoring guide.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """Abstract base class for all shoutrrr-logger plugins."""

    # ------------------------------------------------------------------ #
    # Plugin metadata — must be overridden by subclasses                  #
    # ------------------------------------------------------------------ #

    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique snake_case identifier, e.g. ``"splunk"``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name shown in the admin UI."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description of what this plugin does."""

    @property
    @abstractmethod
    def default_config(self) -> dict[str, Any]:
        """
        Default configuration values.  Every key that the plugin reads from
        ``config`` must appear here so the admin UI can build the form.
        """

    # ------------------------------------------------------------------ #
    # Plugin lifecycle                                                     #
    # ------------------------------------------------------------------ #

    @abstractmethod
    async def on_notification(
        self,
        notification: Any,  # schemas.NotificationOut
        config: dict[str, Any],
    ) -> None:
        """
        Called after a notification has been saved to the database.

        Parameters
        ----------
        notification:
            The fully serialised ``NotificationOut`` dict for the saved
            notification, including ``custom_fields``.
        config:
            The merged config dict (``default_config`` overridden by the
            values stored in the database for this plugin).
        """

    # ------------------------------------------------------------------ #
    # Helpers available to subclasses                                     #
    # ------------------------------------------------------------------ #

    def get_config_value(
        self,
        config: dict[str, Any],
        key: str,
        default: Any = None,
    ) -> Any:
        """Return ``config[key]`` falling back to ``self.default_config[key]``."""
        return config.get(key, self.default_config.get(key, default))

    def log(self, message: str, level: str = "info") -> None:
        """Convenience logger that prefixes the plugin id."""
        getattr(logger, level, logger.info)(f"[plugin:{self.plugin_id}] {message}")
