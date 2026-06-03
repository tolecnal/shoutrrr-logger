"""
Plugin registry — discovers and manages all installed plugins.

Discovery strategy (in order):
  1. Sub-packages — any directory inside ``plugins/`` that contains both
     an ``__init__.py`` and a ``plugin.py`` is treated as a self-contained
     plugin package.  The registry imports ``plugins.<name>`` and looks for
     a ``BasePlugin`` subclass in the resulting module namespace.
  2. Flat modules — any ``*.py`` file directly in ``plugins/`` (excluding
     ``base.py`` and ``registry.py``) is imported and scanned for
     ``BasePlugin`` subclasses.  This preserves backward compatibility.

In both cases no explicit registration is needed: just place the file/folder
in the ``plugins/`` directory and restart the application.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING

from plugins.base import BasePlugin

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# plugin_id → plugin instance
_REGISTRY: dict[str, BasePlugin] = {}

_SKIP_MODULES = frozenset({"base", "registry"})


def _register_from_module(mod: object, source: str) -> None:
    """Scan *mod* for BasePlugin subclasses and add them to _REGISTRY."""
    for attr in vars(mod).values():
        if (
            isinstance(attr, type)
            and issubclass(attr, BasePlugin)
            and attr is not BasePlugin
            and not inspect.isabstract(attr)
        ):
            try:
                instance: BasePlugin = attr()
                pid = instance.plugin_id
                if pid not in _REGISTRY:
                    _REGISTRY[pid] = instance
                    logger.info(
                        "Registered plugin '%s' (%s) from %s",
                        pid, instance.name, source,
                    )
            except Exception as exc:
                logger.error(
                    "Failed to instantiate plugin class %s from %s: %s",
                    attr.__name__, source, exc,
                )


def discover() -> None:
    """
    Discover and register all plugins.  Safe to call multiple times —
    already-registered plugins are skipped.
    """
    import plugins as _pkg  # the package itself  # noqa: PLC0415

    plugins_path = Path(_pkg.__file__).parent

    for entry in pkgutil.iter_modules([str(plugins_path)]):
        name: str = entry.name
        is_pkg: bool = entry.ispkg

        if name in _SKIP_MODULES:
            continue

        full_name = f"plugins.{name}"

        if is_pkg:
            # Sub-package — self-contained plugin folder.
            # Import the package (triggers __init__.py) then scan for subclasses.
            try:
                mod = importlib.import_module(full_name)
                _register_from_module(mod, source=f"{name}/__init__.py")

                # Also import plugin.py directly if __init__.py didn't re-export it
                plugin_mod_name = f"{full_name}.plugin"
                if importlib.util.find_spec(plugin_mod_name):
                    plugin_mod = importlib.import_module(plugin_mod_name)
                    _register_from_module(plugin_mod, source=f"{name}/plugin.py")
            except Exception as exc:
                logger.error(
                    "Failed to import plugin package '%s': %s", name, exc
                )
        else:
            # Flat .py file — legacy / simple plugin.
            try:
                mod = importlib.import_module(full_name)
                _register_from_module(mod, source=f"{name}.py")
            except Exception as exc:
                logger.error(
                    "Failed to import plugin module '%s': %s", name, exc
                )


def all_plugins() -> list[BasePlugin]:
    """Return all registered plugin instances in registration order."""
    return list(_REGISTRY.values())


def get_plugin(plugin_id: str) -> BasePlugin | None:
    """Return the plugin instance for *plugin_id*, or ``None`` if not found."""
    return _REGISTRY.get(plugin_id)
