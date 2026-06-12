"use client";

import { useState } from "react";
import useSWR from "swr";
import { Puzzle } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchPlugins,
  fetchCustomFieldKeys,
  updatePlugin,
  createPluginProfile,
  updatePluginProfile,
  deletePluginProfile,
  testPluginProfile,
} from "@/lib/api";
import type { PluginMeta } from "@/lib/types";
import {
  PluginCardHeader,
  PluginProfileTabs,
  type ProfileApi,
} from "@/components/plugin-profile-tabs";

const adminProfileApi: ProfileApi = {
  create: createPluginProfile,
  update: updatePluginProfile,
  remove: deletePluginProfile,
  test: testPluginProfile,
};

// ---------------------------------------------------------------------------
// Per-plugin card — global profiles + plugin-level settings
// ---------------------------------------------------------------------------

function PluginCard({
  plugin,
  availableCustomFields,
  onSaved,
}: {
  plugin: PluginMeta;
  availableCustomFields: string[];
  onSaved: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [allowUserConfigs, setAllowUserConfigs] = useState(plugin.allow_user_configs ?? true);
  const [allowSaving, setAllowSaving] = useState(false);

  const enabledCount = plugin.profiles.filter((p) => p.enabled).length;

  async function handleAllowUserConfigs(value: boolean): Promise<void> {
    setAllowUserConfigs(value);
    setAllowSaving(true);
    try {
      await updatePlugin(plugin.id, { allow_user_configs: value });
      onSaved();
    } catch {
      setAllowUserConfigs(!value); // revert on failure
    } finally {
      setAllowSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <PluginCardHeader
        name={plugin.name}
        description={plugin.description}
        enabledCount={enabledCount}
        expanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
      />

      {expanded && (
        <>
          <Separator />
          <div className="px-4 py-4 space-y-6">
            <div className="flex items-center justify-between rounded-lg border p-3 shadow-sm">
              <div className="space-y-0.5">
                <p className="text-sm font-medium">Allow User Configurations</p>
                <p className="text-xs text-muted-foreground">
                  Allow regular users to configure this plugin with their own private settings.
                </p>
              </div>
              <Switch
                checked={allowUserConfigs}
                disabled={allowSaving}
                onCheckedChange={(v) => void handleAllowUserConfigs(v)}
              />
            </div>
            <Separator />
            <PluginProfileTabs
              pluginId={plugin.id}
              pluginName={plugin.name}
              profiles={plugin.profiles}
              maxProfiles={0}
              availableCustomFields={availableCustomFields}
              api={adminProfileApi}
              onSaved={onSaved}
            />
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plugins tab root
// ---------------------------------------------------------------------------

export function PluginsTab() {
  const { data: customFields = [] } = useSWR<string[]>(
    "/api/v1/admin/plugins/custom-field-keys",
    fetchCustomFieldKeys,
    { revalidateOnFocus: false }
  );

  const { data: plugins, mutate: mutatePlugins } = useSWR("/admin/plugins", fetchPlugins, {
    revalidateOnFocus: false
  });

  if (!plugins) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-14 w-full rounded-lg" />
        <Skeleton className="h-14 w-full rounded-lg" />
      </div>
    );
  }

  if (!plugins?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
        <Puzzle className="h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">No plugins registered.</p>
        <p className="text-xs text-muted-foreground max-w-xs">
          Drop a plugin folder into{" "}
          <code className="font-mono">backend/plugins/</code> and restart the
          application. See <code className="font-mono">PLUGINS.md</code> for the
          authoring guide.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {plugins.map((p) => (
        <PluginCard
          key={p.id}
          plugin={p}
          availableCustomFields={customFields}
          onSaved={() => mutatePlugins()}
        />
      ))}
    </div>
  );
}
