"use client";

/**
 * Shared profile-tabs UI for plugin configuration profiles.
 *
 * Used by both Preferences → My Plugins (per-user profiles) and
 * Admin → Plugins (global profiles); the caller supplies a `ProfileApi`
 * adapter wiring the CRUD/test calls to the right endpoints.
 */

import { Suspense, useState } from "react";
import { ChevronDown, Save, Plus, Trash2, Pencil, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import type { PluginProfileOut } from "@/lib/types";
import { PLUGIN_CONFIG_PANELS } from "@/plugins/registry";
import { RoutingRulesEditor } from "@/components/routing-rules-editor";

export interface ProfileApi {
  create(pluginId: string, body: { name: string; copy_from?: string }): Promise<PluginProfileOut>;
  update(
    pluginId: string,
    profileId: string,
    updates: { name?: string; enabled?: boolean; config?: Record<string, unknown>; rules?: any[] }
  ): Promise<PluginProfileOut>;
  remove(pluginId: string, profileId: string): Promise<void>;
  test(pluginId: string, profileId: string): Promise<{ detail: string }>;
}

function ProfileEditor({
  pluginId,
  profile,
  availableCustomFields,
  canDelete,
  api,
  onSaved,
}: {
  pluginId: string;
  profile: PluginProfileOut;
  availableCustomFields: string[];
  canDelete: boolean;
  api: ProfileApi;
  onSaved: () => void;
}) {
  const [enabled, setEnabled] = useState(profile.enabled);
  const [config, setConfig] = useState<Record<string, unknown>>(profile.config);
  const [rules, setRules] = useState<any[]>(profile.rules ?? []);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState(profile.name);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const ConfigPanel = PLUGIN_CONFIG_PANELS[pluginId] ?? null;

  const dirty =
    enabled !== profile.enabled ||
    JSON.stringify(config) !== JSON.stringify(profile.config) ||
    JSON.stringify(rules) !== JSON.stringify(profile.rules ?? []);

  async function handleSave(): Promise<void> {
    setSaving(true);
    setSaveMsg(null);
    try {
      await api.update(pluginId, profile.id, { enabled, config, rules });
      setSaveMsg("Saved.");
      onSaved();
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(): Promise<void> {
    const res = await api.test(pluginId, profile.id);
    if (!res.detail?.toLowerCase().includes("sent")) {
      throw new Error(res.detail ?? "Unknown error");
    }
  }

  async function handleRename(): Promise<void> {
    const name = renameValue.trim();
    if (!name || name === profile.name) {
      setRenameOpen(false);
      return;
    }
    try {
      await api.update(pluginId, profile.id, { name });
      setRenameOpen(false);
      onSaved();
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Rename failed.");
      setRenameOpen(false);
    }
  }

  async function handleDelete(): Promise<void> {
    try {
      await api.remove(pluginId, profile.id);
      onSaved();
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Delete failed.");
    }
  }

  return (
    <div className="space-y-5">
      {/* Profile toolbar */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <Switch checked={enabled} onCheckedChange={(v) => { setEnabled(v); setSaveMsg(null); }} />
          <span className="text-sm text-muted-foreground">
            {enabled ? "Profile active" : "Profile disabled"}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {saveMsg && !dirty && <span className="text-xs text-muted-foreground mr-1">{saveMsg}</span>}
          {dirty && (
            <Button size="sm" onClick={() => void handleSave()} disabled={saving} className="h-7 text-xs gap-1">
              <Save className="h-3 w-3" />
              {saving ? "Saving…" : "Save"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            title="Rename profile"
            onClick={() => { setRenameValue(profile.name); setRenameOpen(true); }}
          >
            <Pencil className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
            title="Delete profile"
            disabled={!canDelete}
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <RoutingRulesEditor rules={rules} onChange={(next) => { setRules(next); setSaveMsg(null); }} />
      <Separator />
      {ConfigPanel && (
        <Suspense fallback={<Skeleton className="h-40 w-full" />}>
          <ConfigPanel
            config={config}
            onChange={(next) => { setConfig(next); setSaveMsg(null); }}
            onTest={handleTest}
            saving={saving}
            availableCustomFields={availableCustomFields}
          />
        </Suspense>
      )}

      {/* Rename dialog */}
      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Rename profile</DialogTitle>
          </DialogHeader>
          <div className="py-2 space-y-1.5">
            <Label htmlFor="profile-rename">Name</Label>
            <Input
              id="profile-rename"
              name="profile-rename"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void handleRename(); }}
              autoFocus
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameOpen(false)}>Cancel</Button>
            <Button onClick={() => void handleRename()} disabled={!renameValue.trim()}>Rename</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete profile "{profile.name}"?</AlertDialogTitle>
            <AlertDialogDescription>
              The profile's configuration and routing rules are permanently removed.
              Notifications will no longer be delivered through it.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void handleDelete()}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export function PluginProfileTabs({
  pluginId,
  pluginName,
  profiles,
  maxProfiles,
  availableCustomFields,
  api,
  onSaved,
}: {
  pluginId: string;
  pluginName: string;
  profiles: PluginProfileOut[];
  /** 0 = unlimited */
  maxProfiles: number;
  availableCustomFields: string[];
  api: ProfileApi;
  onSaved: () => void;
}) {
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [addName, setAddName] = useState("");
  const [addCopy, setAddCopy] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const atCap = maxProfiles > 0 && profiles.length >= maxProfiles;
  const activeId =
    activeProfileId && profiles.some((p) => p.id === activeProfileId)
      ? activeProfileId
      : profiles[0]?.id;

  async function handleAdd(): Promise<void> {
    const name = addName.trim();
    if (!name) return;
    setAdding(true);
    setAddError(null);
    try {
      const created = await api.create(pluginId, {
        name,
        ...(addCopy && activeId ? { copy_from: activeId } : {}),
      });
      setAddOpen(false);
      setAddName("");
      setAddCopy(false);
      setActiveProfileId(created.id);
      onSaved();
    } catch (e) {
      setAddError(e instanceof Error ? e.message : "Failed to create profile.");
    } finally {
      setAdding(false);
    }
  }

  return (
    <>
      <Tabs value={activeId} onValueChange={setActiveProfileId}>
        <div className="flex items-center gap-2 mb-4">
          <TabsList className="h-8 overflow-x-auto justify-start">
            {profiles.map((p) => (
              <TabsTrigger key={p.id} value={p.id} className="h-7 text-xs gap-1.5">
                {p.name}
                <span
                  className={cn(
                    "inline-block h-1.5 w-1.5 rounded-full",
                    p.enabled ? "bg-green-500" : "bg-muted-foreground/30"
                  )}
                />
              </TabsTrigger>
            ))}
          </TabsList>
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs gap-1 shrink-0"
            disabled={atCap}
            title={
              atCap
                ? `Profile limit reached (${maxProfiles} per plugin). Ask an administrator to raise it.`
                : "Add a profile"
            }
            onClick={() => setAddOpen(true)}
          >
            <Plus className="h-3 w-3" />
            Add profile
          </Button>
        </div>
        {profiles.map((p) => (
          <TabsContent key={p.id} value={p.id} className="mt-0">
            <ProfileEditor
              // Remount the editor when saved server state changes so
              // local draft state resets to what the server returned.
              key={`${p.id}:${JSON.stringify(p)}`}
              pluginId={pluginId}
              profile={p}
              availableCustomFields={availableCustomFields}
              canDelete={profiles.length > 1}
              api={api}
              onSaved={onSaved}
            />
          </TabsContent>
        ))}
      </Tabs>

      {/* Add-profile dialog */}
      <Dialog open={addOpen} onOpenChange={(o) => { setAddOpen(o); if (!o) setAddError(null); }}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>New {pluginName} profile</DialogTitle>
          </DialogHeader>
          <div className="py-2 space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="profile-add-name">Name</Label>
              <Input
                id="profile-add-name"
                name="profile-add-name"
                placeholder="e.g. Ops channel"
                value={addName}
                onChange={(e) => setAddName(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void handleAdd(); }}
                autoFocus
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
              <input
                id="profile-add-copy"
                name="profile-add-copy"
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={addCopy}
                onChange={(e) => setAddCopy(e.target.checked)}
              />
              <span className="flex items-center gap-1.5">
                <Copy className="h-3.5 w-3.5" />
                Copy settings and rules from the current profile
              </span>
            </label>
            {addError && <p className="text-sm text-destructive">{addError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={() => void handleAdd()} disabled={!addName.trim() || adding}>
              {adding ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Shared expandable card header used by both plugin tabs. */
export function PluginCardHeader({
  name,
  description,
  enabledCount,
  expanded,
  onToggle,
}: {
  name: string;
  description: string;
  enabledCount: number;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-3 px-4 py-3 cursor-pointer select-none hover:bg-muted/30 transition-colors rounded-t-lg",
        expanded && "rounded-b-none"
      )}
      onClick={onToggle}
    >
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground leading-none">{name}</p>
        <p className="text-xs text-muted-foreground mt-0.5 truncate">{description}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {enabledCount > 0 && (
          <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-normal text-secondary-foreground">
            {enabledCount} active {enabledCount === 1 ? "profile" : "profiles"}
          </span>
        )}
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform duration-200",
            !expanded && "-rotate-90"
          )}
        />
      </div>
    </div>
  );
}
