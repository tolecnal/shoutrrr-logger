"use client";

import { Suspense, useState } from "react";
import useSWR from "swr";
import { Puzzle, ChevronDown, ChevronRight, Save } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchPlugins, fetchCustomFieldKeys, updatePlugin, testPlugin } from "@/lib/api";
import type { PluginMeta } from "@/lib/types";
import { PLUGIN_CONFIG_PANELS } from "@/plugins/registry";

// ---------------------------------------------------------------------------
// Per-plugin card — owns all local edit state for that plugin
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
  const [enabled, setEnabled] = useState(plugin.enabled);
  const [config, setConfig] = useState<Record<string, unknown>>(plugin.config);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const ConfigPanel = PLUGIN_CONFIG_PANELS[plugin.id] ?? null;

  const dirty =
    enabled !== plugin.enabled ||
    JSON.stringify(config) !== JSON.stringify(plugin.config);

  async function handleSave() {
    setSaving(true);
    setSaveMsg(null);
    try {
      await updatePlugin(plugin.id, { enabled, config });
      setSaveMsg("Saved.");
      onSaved();
    } catch (e: unknown) {
      setSaveMsg(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    const res = await testPlugin(plugin.id);
    if (!res.detail?.toLowerCase().includes("sent")) {
      throw new Error(res.detail ?? "Unknown error");
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      {/* Header row */}
      <div className="flex items-center gap-3 px-4 py-3">
        <Switch
          checked={enabled}
          onCheckedChange={(v) => {
            setEnabled(v);
            setSaveMsg(null);
          }}
          aria-label={`Enable ${plugin.name}`}
        />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground leading-none">{plugin.name}</p>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{plugin.description}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {saveMsg && !dirty && (
            <span className="text-xs text-muted-foreground">{saveMsg}</span>
          )}
          {dirty && (
            <Button
              size="sm"
              variant="default"
              onClick={handleSave}
              disabled={saving}
              className="h-7 text-xs gap-1"
            >
              <Save className="h-3 w-3" />
              {saving ? "Saving…" : "Save"}
            </Button>
          )}
          {ConfigPanel && (
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-muted-foreground hover:text-foreground transition-colors"
              aria-label={expanded ? "Collapse config" : "Expand config"}
            >
              {expanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </button>
          )}
        </div>
      </div>

      {/* Config panel — lazy-loaded from the plugin registry */}
      {ConfigPanel && expanded && (
        <>
          <Separator />
          <div className="px-4 py-4">
            <Suspense fallback={<Skeleton className="h-40 w-full" />}>
              <ConfigPanel
                config={config}
                onChange={(next) => {
                  setConfig(next);
                  setSaveMsg(null);
                }}
                onTest={handleTest}
                saving={saving}
                availableCustomFields={availableCustomFields}
              />
            </Suspense>
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
  const {
    data: plugins,
    isLoading,
    mutate,
  } = useSWR<PluginMeta[]>("/api/admin/plugins", fetchPlugins, {
    revalidateOnFocus: false,
  });

  const { data: customFieldKeys = [] } = useSWR<string[]>(
    "/api/admin/plugins/custom-field-keys",
    fetchCustomFieldKeys,
    { revalidateOnFocus: false }
  );

  if (isLoading) {
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
      {plugins.map((plugin) => (
        <PluginCard
          key={plugin.id}
          plugin={plugin}
          availableCustomFields={customFieldKeys}
          onSaved={() => mutate()}
        />
      ))}
    </div>
  );
}
