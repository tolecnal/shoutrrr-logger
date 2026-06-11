"use client";

import { Suspense, useState } from "react";
import useSWR from "swr";
import { Puzzle, ChevronDown, Save } from "lucide-react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchUserPlugins, updateUserPlugin, fetchCustomFieldKeys, testPlugin } from "@/lib/api";
import type { UserPluginOut, RoutingRuleOut } from "@/lib/types";
import { PLUGIN_CONFIG_PANELS } from "@/plugins/registry";
import { RoutingRulesEditor } from "@/components/routing-rules-editor";

function UserPluginCard({
  userPlugin,
  availableCustomFields,
  onSaved,
}: {
  userPlugin: UserPluginOut;
  availableCustomFields: string[];
  onSaved: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [enabled, setEnabled] = useState(userPlugin.enabled);
  const [config, setConfig] = useState<Record<string, unknown>>(userPlugin.config);
  const [rules, setRules] = useState<any[]>(userPlugin.rules ?? []);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const ConfigPanel = PLUGIN_CONFIG_PANELS[userPlugin.plugin_id] ?? null;

  const dirty =
    enabled !== userPlugin.enabled ||
    JSON.stringify(config) !== JSON.stringify(userPlugin.config) ||
    JSON.stringify(rules) !== JSON.stringify(userPlugin.rules ?? []);

  async function handleSave() {
    setSaving(true);
    setSaveMsg(null);
    try {
      await updateUserPlugin(userPlugin.plugin_id, { enabled, config, rules });
      setSaveMsg("Saved.");
      onSaved();
    } catch (e: any) {
      setSaveMsg(e.message ?? "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    const res = await testPlugin(userPlugin.plugin_id);
    if (!res.detail?.toLowerCase().includes("sent")) {
      throw new Error(res.detail ?? "Unknown error");
    }
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-3",
          ConfigPanel && "cursor-pointer select-none hover:bg-muted/30 transition-colors rounded-t-lg",
          ConfigPanel && expanded && "rounded-b-none"
        )}
        onClick={ConfigPanel ? () => setExpanded((v) => !v) : undefined}
      >
        <div onClick={(e) => e.stopPropagation()}>
          <Switch
            checked={enabled}
            onCheckedChange={(v) => {
              setEnabled(v);
              setSaveMsg(null);
            }}
          />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground leading-none">{userPlugin.name}</p>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{userPlugin.description}</p>
        </div>
        <div
          className="flex items-center gap-2 shrink-0"
          onClick={(e) => e.stopPropagation()}
        >
          {saveMsg && !dirty && <span className="text-xs text-muted-foreground">{saveMsg}</span>}
          {dirty && (
            <Button size="sm" onClick={handleSave} disabled={saving} className="h-7 text-xs gap-1">
              <Save className="h-3 w-3" />
              {saving ? "Saving…" : "Save"}
            </Button>
          )}
          {ConfigPanel && (
            <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform duration-200", !expanded && "-rotate-90")} />
          )}
        </div>
      </div>

      {ConfigPanel && expanded && (
        <>
          <Separator />
          <div className="px-4 py-4 space-y-6">
            <RoutingRulesEditor
              rules={rules}
              onChange={(next) => {
                setRules(next);
                setSaveMsg(null);
              }}
            />
            <Separator />
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

export function UserPluginsTab() {
  const { data: userPlugins, isLoading, mutate } = useSWR<UserPluginOut[]>("/api/v1/user-plugins", fetchUserPlugins, { revalidateOnFocus: false });
  const { data: customFieldKeys = [] } = useSWR<string[]>("/api/admin/plugins/custom-field-keys", fetchCustomFieldKeys, { revalidateOnFocus: false });

  if (isLoading) {
    return (
      <div className="space-y-3 mt-4">
        <Skeleton className="h-14 w-full rounded-lg" />
        <Skeleton className="h-14 w-full rounded-lg" />
      </div>
    );
  }

  if (!userPlugins?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
        <Puzzle className="h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">No plugins available.</p>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto mt-4 pr-1 space-y-3">
      {userPlugins.map((plugin) => (
        <UserPluginCard
          key={plugin.plugin_id}
          userPlugin={plugin}
          availableCustomFields={customFieldKeys}
          onSaved={() => mutate()}
        />
      ))}
    </div>
  );
}
