# Plugin Authoring Guide

Plugins allow you to react to every incoming notification — forward it to an
external system, transform it, trigger an alert, etc.  Each plugin is fully
**self-contained in its own folder**.  Adding a plugin to the application
requires touching only one file outside the plugin folder:

| File | Change |
|------|--------|
| `frontend/plugins/registry.tsx` | Add one line mapping `plugin_id → React component` |

If your plugin has no configurable settings, even that step is optional.

---

## Folder layout

```
backend/plugins/<plugin_id>/
    __init__.py      # re-exports the plugin class (required)
    plugin.py        # plugin logic — subclasses BasePlugin
    README.md        # optional per-plugin docs

frontend/plugins/<plugin_id>/
    config.tsx       # React config panel (optional — omit if no settings)
    types.ts         # TypeScript types for this plugin (optional)
```

---

## Backend — `plugin.py`

Your plugin class must subclass `BasePlugin` and implement four properties
plus one async method:

```python
# backend/plugins/my_plugin/plugin.py
from __future__ import annotations
from typing import Any
from plugins.base import BasePlugin


class MyPlugin(BasePlugin):

    @property
    def plugin_id(self) -> str:
        return "my_plugin"           # unique snake_case id

    @property
    def name(self) -> str:
        return "My Plugin"           # shown in the admin UI

    @property
    def description(self) -> str:
        return "Does something useful with each notification."

    @property
    def default_config(self) -> dict[str, Any]:
        # Every key the plugin reads from config MUST be listed here.
        # These values are shown in the admin UI as the initial state.
        return {
            "webhook_url": "",
            "include_title": True,
        }

    async def on_notification(
        self,
        notification: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        """
        Called after every notification is saved to the database.

        Parameters
        ----------
        notification
            Fully serialised NotificationOut dict.  Always contains:
              id, sender_name, title, message, received_at, source_ip,
              custom_fields (dict of any extra fields sent by shoutrrr).
        config
            Merged config: default_config overridden by admin-saved values.
        """
        webhook_url = config.get("webhook_url", "").strip()
        if not webhook_url:
            self.log("webhook_url not configured — skipping", "warning")
            return

        # self.log() prefixes the plugin_id automatically
        self.log(f"Forwarding notification {notification['id']}")
        # ... do work here ...
```

### `__init__.py`

Re-export the class so the registry can find it:

```python
# backend/plugins/my_plugin/__init__.py
from plugins.my_plugin.plugin import MyPlugin

__all__ = ["MyPlugin"]
```

### Discovery

At startup `registry.discover()` scans every sub-package (directory with
`__init__.py`) and every flat `.py` file inside `backend/plugins/`.  It
instantiates any concrete `BasePlugin` subclass it finds.  No registration
call is needed — just place the folder there and restart.

### Accessing `custom_fields`

Fields sent by shoutrrr as query parameters (e.g. `?$hostname=server01`) are
stripped of their `$` prefix and stored under `notification["custom_fields"]`:

```python
hostname = (notification.get("custom_fields") or {}).get("hostname")
```

### Source field syntax (for field-mapping plugins like Splunk)

| Syntax | Example | Resolves to |
|--------|---------|-------------|
| Top-level key | `message` | `notification["message"]` |
| Custom field | `custom_fields.hostname` | `notification["custom_fields"]["hostname"]` |
| Literal | `literal:production` | the string `"production"` |

---

## Frontend — `config.tsx`

If your plugin has user-configurable settings, provide a React component.
It must satisfy the `PluginConfigProps` interface from `frontend/plugins/types.ts`:

```tsx
// frontend/plugins/my_plugin/config.tsx
"use client";

import type { PluginConfigProps } from "@/plugins/types";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function MyPluginConfigPanel({
  config,
  onChange,
  onTest,
  saving,
  availableCustomFields,  // distinct custom_fields keys from recent notifications
}: PluginConfigProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <Label className="text-xs">Webhook URL</Label>
        <Input
          value={String(config.webhook_url ?? "")}
          onChange={(e) => onChange({ ...config, webhook_url: e.target.value })}
          placeholder="https://..."
          className="h-7 text-xs"
        />
      </div>
      <button onClick={onTest} disabled={saving}>
        Send test
      </button>
    </div>
  );
}
```

### `PluginConfigProps` contract

| Prop | Type | Description |
|------|------|-------------|
| `config` | `Record<string, unknown>` | Merged config (defaults + saved values) |
| `onChange` | `(next) => void` | Call with the full updated config on every change |
| `onTest` | `() => Promise<void>` | Trigger a test notification through the backend |
| `saving` | `boolean` | True while a save/test request is in-flight |
| `availableCustomFields` | `string[]` | Distinct `custom_fields` keys from recent notifications |

**Important**: the component must not call the API directly.  All persistence
is handled by `admin-plugins-tab` via `onChange` / `onTest`.

### Register the component

Add one line to `frontend/plugins/registry.tsx`:

```tsx
export const PLUGIN_CONFIG_PANELS: Record<string, ComponentType<PluginConfigProps>> = {
  splunk:    lazy(() => import("./splunk/config").then(m => ({ default: m.SplunkConfigPanel }))),
  my_plugin: lazy(() => import("./my_plugin/config").then(m => ({ default: m.MyPluginConfigPanel }))),
  //         ^^^^ add this line
};
```

Components are lazy-loaded — unused plugin bundles are never sent to the browser.
If a plugin has no `config.tsx`, simply omit it from this map and the admin UI
will show no expand arrow for that plugin.

---

## Complete example — Echo plugin

A minimal plugin that logs every notification to the application log.

### `backend/plugins/echo/__init__.py`

```python
from plugins.echo.plugin import EchoPlugin
__all__ = ["EchoPlugin"]
```

### `backend/plugins/echo/plugin.py`

```python
from __future__ import annotations
import json
from typing import Any
from plugins.base import BasePlugin


class EchoPlugin(BasePlugin):
    @property
    def plugin_id(self) -> str:
        return "echo"

    @property
    def name(self) -> str:
        return "Echo"

    @property
    def description(self) -> str:
        return "Logs every notification to the application log (useful for debugging)."

    @property
    def default_config(self) -> dict[str, Any]:
        return {"include_custom_fields": True}

    async def on_notification(
        self, notification: dict[str, Any], config: dict[str, Any]
    ) -> None:
        fields = notification.get("custom_fields") or {}
        custom = f" custom_fields={json.dumps(fields)}" if (
            config.get("include_custom_fields") and fields
        ) else ""
        self.log(
            f"[{notification['id']}] {notification.get('sender_name')} — "
            f"{notification.get('message', '')[:80]}{custom}"
        )
```

No `frontend/plugins/echo/` folder is needed — a plugin with no configurable
settings simply has no config panel, and the admin UI will not show an expand
arrow for it.

---

## Error handling

If `on_notification` raises an exception, the error is logged at `ERROR` level
and the next plugin continues.  A plugin failure never affects the HTTP
response returned to the shoutrrr caller, and the notification is always saved
to the database before plugins run.

The `POST /api/admin/plugins/{id}/test` endpoint surfaces errors directly to
the admin UI so you can test your plugin configuration interactively.

---

## Config persistence

Configs are stored in the `plugin_configs` database table as a JSONB column.
Only keys that differ from `default_config` are stored; the defaults are merged
at runtime.  All plugin API endpoints require the `admin` role:

```
GET   /api/admin/plugins
GET   /api/admin/plugins/{id}
PATCH /api/admin/plugins/{id}             body: { "enabled": bool, "config": {...} }
POST  /api/admin/plugins/{id}/test
GET   /api/admin/plugins/custom-field-keys   returns distinct custom_fields keys
```

---

## Shipping plugins in Docker

Plugins are part of the application source tree, so they are included
automatically in the Docker image build.  No additional steps are needed.

If you maintain private plugins outside the main repository, mount them into
the container:

```yaml
# docker-compose.yml
services:
  app:
    volumes:
      - ./my-private-plugins:/app/backend/plugins/my_plugin
```
