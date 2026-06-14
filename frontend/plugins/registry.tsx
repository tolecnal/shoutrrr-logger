/**
 * Frontend plugin registry.
 *
 * Maps each plugin_id to its React config panel component.
 * This is the ONLY file that needs to be edited when adding a new plugin.
 *
 * To add a plugin:
 *   1. Create frontend/plugins/<id>/config.tsx exporting a component
 *      that satisfies PluginConfigProps (see plugins/types.ts).
 *   2. Add one line below: `  <id>: lazy(() => import("./<id>/config").then(m => ({ default: m.<Component> }))),`
 *
 * Components are lazy-loaded so unused plugin bundles are never sent to the browser.
 */

import { lazy, type ComponentType } from "react";
import type { PluginConfigProps } from "./types";

export const PLUGIN_CONFIG_PANELS: Record<string, ComponentType<PluginConfigProps>> = {
  splunk: lazy(() =>
    import("./splunk/config").then((m) => ({ default: m.SplunkConfigPanel }))
  ),
  slack: lazy(() =>
    import("./slack/config").then((m) => ({ default: m.SlackConfigPanel }))
  ),
  webhook: lazy(() =>
    import("./webhook/config").then((m) => ({ default: m.WebhookConfigPanel }))
  ),
  ntfy: lazy(() =>
    import("./ntfy/config").then((m) => ({ default: m.NtfyConfigPanel }))
  ),
  pushover: lazy(() =>
    import("./pushover/config").then((m) => ({ default: m.PushoverConfigPanel }))
  ),
  discord: lazy(() =>
    import("./discord/config").then((m) => ({ default: m.DiscordConfigPanel }))
  ),
  telegram: lazy(() =>
    import("./telegram/config").then((m) => ({ default: m.TelegramConfigPanel }))
  ),
  gotify: lazy(() =>
    import("./gotify/config").then((m) => ({ default: m.GotifyConfigPanel }))
  ),
  pagerduty: lazy(() =>
    import("./pagerduty/config").then((m) => ({ default: m.PagerDutyConfigPanel }))
  ),
  teams: lazy(() =>
    import("./teams/config").then((m) => ({ default: m.TeamsConfigPanel }))
  ),
  matrix: lazy(() =>
    import("./matrix/config").then((m) => ({ default: m.MatrixConfigPanel }))
  ),
};
