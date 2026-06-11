"use client";

import { useState, useEffect } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { fetchAdminSettings, updateSettings } from "@/lib/api";
import type { SettingOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function SettingsTab() {
  const { data, isLoading, mutate } = useSWR<SettingOut[]>(
    "/admin/settings",
    fetchAdminSettings
  );

  const [draft, setDraft] = useState<Record<string, number>>({});
  const [saving, setSaving] = useState(false);

  // Sync draft whenever server data arrives (first load or after save)
  useEffect(() => {
    if (data) {
      const next: Record<string, number> = {};
      for (const s of data) next[s.key] = s.value;
      setDraft(next);
    }
  }, [data]);

  const isDirty = data
    ? data.some((s) => draft[s.key] !== undefined && draft[s.key] !== s.value)
    : false;

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updateSettings(draft);
      await mutate(updated, { revalidate: false });
      // Invalidate the public /settings cache so stats panel and notification
      // log pick up the new values without a full page reload.
      await globalMutate("/settings");
      toast.success("Settings saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (isLoading || !data) {
    return (
      <div className="space-y-4 max-w-lg">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <Skeleton className="h-3 w-32" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-3 w-64" />
          </div>
        ))}
      </div>
    );
  }

  // Helper to render a setting
  const renderSetting = (key: string) => {
    const setting = data.find((s) => s.key === key);
    if (!setting) return null;

    const val = draft[setting.key] ?? setting.value;
    const changed = val !== setting.value;

    if (setting.value_type === "bool") {
      return (
        <div key={setting.key} className="space-y-1.5 p-4 rounded-md border border-border/50 bg-muted/20">
          <div className="flex items-center justify-between gap-4">
            <label
              htmlFor={`setting-${setting.key}`}
              className="text-sm font-medium text-foreground"
            >
              {setting.label}
            </label>
            <Switch
              id={`setting-${setting.key}`}
              checked={val !== 0}
              onCheckedChange={(checked) =>
                setDraft((prev) => ({ ...prev, [setting.key]: checked ? 1 : 0 }))
              }
              className={changed ? "ring-2 ring-primary/50" : ""}
            />
          </div>
          <p className="text-xs text-muted-foreground">{setting.description}</p>
        </div>
      );
    }

    return (
      <div key={setting.key} className="space-y-1.5 p-4 rounded-md border border-border/50 bg-muted/20">
        <div className="flex items-baseline justify-between">
          <label
            htmlFor={`setting-${setting.key}`}
            className="text-sm font-medium text-foreground"
          >
            {setting.label}
          </label>
          {setting.unit && (
            <span className="text-xs text-muted-foreground">{setting.unit}</span>
          )}
        </div>
        <Input
          id={`setting-${setting.key}`}
          type="number"
          min={setting.min_value}
          max={setting.max_value}
          value={val}
          onChange={(e) => {
            const n = parseInt(e.target.value, 10);
            if (!Number.isNaN(n)) {
              setDraft((prev) => ({ ...prev, [setting.key]: n }));
            }
          }}
          className={changed ? "border-primary/50 bg-primary/5" : ""}
        />
        <p className="text-xs text-muted-foreground">{setting.description}</p>
        {setting.min_value === 0 && setting.key === "retention_days" && (
          <p className="text-xs text-muted-foreground/70 italic">
            Current value: {val === 0 ? "disabled (keep forever)" : `${val} days`}
          </p>
        )}
        {setting.key === "auto_refresh_interval" && (
          <p className="text-xs text-muted-foreground/70 italic">
            Current value: {val === 0 ? "disabled" : `every ${val}s`}
          </p>
        )}
        {setting.key === "stats_window_days" && (
          <p className="text-xs text-muted-foreground/70 italic">
            Cannot exceed Retention period or API metrics retention (when either is
            non-zero).
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="max-w-2xl space-y-6">
      <Tabs defaultValue="ui" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="ui">UI</TabsTrigger>
          <TabsTrigger value="retention">Retention</TabsTrigger>
          <TabsTrigger value="access">Access</TabsTrigger>
        </TabsList>
        <TabsContent value="ui" className="space-y-4">
          {renderSetting("page_size")}
          {renderSetting("auto_refresh_interval")}
        </TabsContent>
        <TabsContent value="retention" className="space-y-4">
          {renderSetting("retention_days")}
          {renderSetting("stats_window_days")}
          {renderSetting("api_metrics_retention_days")}
          {renderSetting("audit_log_retention_days")}
        </TabsContent>
        <TabsContent value="access" className="space-y-4">
          {renderSetting("private_tokens_enabled")}
        </TabsContent>
      </Tabs>

      <div className="pt-2 flex items-center gap-3">
        <Button
          onClick={handleSave}
          disabled={!isDirty || saving}
          size="sm"
          className="gap-1.5"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? "Saving…" : "Save changes"}
        </Button>
        {isDirty && (
          <span className="text-xs text-muted-foreground">Unsaved changes</span>
        )}
      </div>
    </div>
  );
}
