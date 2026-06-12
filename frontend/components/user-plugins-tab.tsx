"use client";

import { Suspense, useState } from "react";
import useSWR from "swr";
import { Puzzle, ChevronDown, Save, Plus, Trash2, Pencil, Copy } from "lucide-react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
import {
  fetchUserPlugins,
  createUserPluginProfile,
  updateUserPluginProfile,
  deleteUserPluginProfile,
  testUserPluginProfile,
  fetchCustomFieldKeys,
} from "@/lib/api";
import type { UserPluginOut, UserPluginProfileOut } from "@/lib/types";
import { PLUGIN_CONFIG_PANELS } from "@/plugins/registry";
import { RoutingRulesEditor } from "@/components/routing-rules-editor";

function ProfileEditor({
  pluginId,
  profile,
  availableCustomFields,
  canDelete,
  onSaved,
}: {
  pluginId: string;
  profile: UserPluginProfileOut;
  availableCustomFields: string[];
  canDelete: boolean;
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
      await updateUserPluginProfile(pluginId, profile.id, { enabled, config, rules });
      setSaveMsg("Saved.");
      onSaved();
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(): Promise<void> {
    const res = await testUserPluginProfile(pluginId, profile.id);
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
      await updateUserPluginProfile(pluginId, profile.id, { name });
      setRenameOpen(false);
      onSaved();
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : "Rename failed.");
      setRenameOpen(false);
    }
  }

  async function handleDelete(): Promise<void> {
    try {
      await deleteUserPluginProfile(pluginId, profile.id);
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
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const [addName, setAddName] = useState("");
  const [addCopy, setAddCopy] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  const profiles = userPlugin.profiles;
  const enabledCount = profiles.filter((p) => p.enabled).length;
  const atCap = userPlugin.max_profiles > 0 && profiles.length >= userPlugin.max_profiles;
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
      const created = await createUserPluginProfile(userPlugin.plugin_id, {
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
    <div className="rounded-lg border border-border bg-card">
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-3 cursor-pointer select-none hover:bg-muted/30 transition-colors rounded-t-lg",
          expanded && "rounded-b-none"
        )}
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground leading-none">{userPlugin.name}</p>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{userPlugin.description}</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {enabledCount > 0 && (
            <Badge variant="secondary" className="text-xs font-normal">
              {enabledCount} active {enabledCount === 1 ? "profile" : "profiles"}
            </Badge>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 text-muted-foreground transition-transform duration-200",
              !expanded && "-rotate-90"
            )}
          />
        </div>
      </div>

      {expanded && (
        <>
          <Separator />
          <div className="px-4 py-4">
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
                      ? `Profile limit reached (${userPlugin.max_profiles} per plugin). Ask an administrator to raise it.`
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
                    pluginId={userPlugin.plugin_id}
                    profile={p}
                    availableCustomFields={availableCustomFields}
                    canDelete={profiles.length > 1}
                    onSaved={onSaved}
                  />
                </TabsContent>
              ))}
            </Tabs>
          </div>

          {/* Add-profile dialog */}
          <Dialog open={addOpen} onOpenChange={(o) => { setAddOpen(o); if (!o) setAddError(null); }}>
            <DialogContent className="sm:max-w-[425px]">
              <DialogHeader>
                <DialogTitle>New {userPlugin.name} profile</DialogTitle>
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
      )}
    </div>
  );
}

export function UserPluginsTab() {
  const { data: userPlugins, isLoading, mutate } = useSWR<UserPluginOut[]>(
    "/api/v1/user-plugins",
    fetchUserPlugins,
    { revalidateOnFocus: false }
  );
  const { data: customFieldKeys = [] } = useSWR<string[]>(
    "/api/v1/admin/plugins/custom-field-keys",
    fetchCustomFieldKeys,
    { revalidateOnFocus: false }
  );

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
