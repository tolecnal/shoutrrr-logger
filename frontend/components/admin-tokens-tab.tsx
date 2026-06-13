"use client";

import { useState } from "react";
import useSWR from "swr";
import { format, isPast } from "date-fns";
import { Plus, Trash2, ToggleLeft, ToggleRight, Loader2, Eye, EyeOff, Pencil, FlaskConical, Save, X } from "lucide-react";
import { toast } from "sonner";
import { fetchTokens, createToken, deleteToken, updateToken } from "@/lib/api";
import { TokenDeliveryToggles } from "@/components/token-delivery-toggles";
import type { AccessTokenCreated, AccessTokenOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CopyButton } from "@/components/copy-button";
import { TokenTestDialog } from "@/components/token-test-dialog";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { useTranslations } from "next-intl";

type RateLimitMode = "default" | "unlimited" | "custom";

function rateLimitToMode(value: number | null): RateLimitMode {
  if (value === null) return "default";
  if (value === 0) return "unlimited";
  return "custom";
}

function formatRateLimit(value: number | null): string {
  if (value === null) return "Default";
  if (value === 0) return "Unlimited";
  return `${value}/min`;
}

function RateLimitFields({
  mode,
  onModeChange,
  value,
  onValueChange,
  idPrefix,
}: {
  mode: RateLimitMode;
  onModeChange: (mode: RateLimitMode) => void;
  value: string;
  onValueChange: (value: string) => void;
  idPrefix: string;
}) {
  const t = useTranslations("AdminTabs.tokens");
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{t('rateLimit')}</Label>
      <RadioGroup value={mode} onValueChange={(v) => onModeChange(v as RateLimitMode)} className="gap-2">
        <div className="flex items-center gap-2">
          <RadioGroupItem value="default" id={`${idPrefix}-rl-default`} />
          <Label htmlFor={`${idPrefix}-rl-default`} className="text-xs font-normal text-muted-foreground">
            {t('useGlobal')}
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="unlimited" id={`${idPrefix}-rl-unlimited`} />
          <Label htmlFor={`${idPrefix}-rl-unlimited`} className="text-xs font-normal text-muted-foreground">
            {t('unlimited')}
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="custom" id={`${idPrefix}-rl-custom`} />
          <Label htmlFor={`${idPrefix}-rl-custom`} className="text-xs font-normal text-muted-foreground">
            {t('custom')}
          </Label>
          <Input
            id={`${idPrefix}-rl-custom-value`}
            name={`${idPrefix}-rl-custom-value`}
            className="h-7 w-24 text-xs"
            type="number"
            min={1}
            placeholder={t('rateLimitPlaceholder')}
            value={value}
            disabled={mode !== "custom"}
            onChange={(e) => onValueChange(e.target.value)}
            onFocus={() => onModeChange("custom")}
          />
        </div>
      </RadioGroup>
    </div>
  );
}

function tokenStatus(t: AccessTokenOut) {
  if (!t.is_active) return { label: "inactive", variant: "destructive" as const };
  if (t.expires_at && isPast(new Date(t.expires_at))) return { label: "expired", variant: "destructive" as const };
  return { label: "active", variant: "outline" as const };
}

export function TokensTab() {
  const t = useTranslations("AdminTabs.tokens");
  const { data: tokens, isLoading, mutate } = useSWR("/admin/tokens", fetchTokens);

  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<AccessTokenCreated | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<AccessTokenOut | null>(null);
  const [editing, setEditing] = useState<AccessTokenOut | null>(null);
  const [saving, setSaving] = useState(false);

  const [form, setForm] = useState({
    name: "",
    expires_at: "",
    rateLimitMode: "default" as RateLimitMode,
    rateLimitValue: "",
    allow_plugin_dispatch: true,
    allow_email_alerts: true,
  });

  const [editForm, setEditForm] = useState({
    name: "",
    rateLimitMode: "default" as RateLimitMode,
    rateLimitValue: "",
    allow_plugin_dispatch: true,
    allow_email_alerts: true,
  });

  const handleCreate = async () => {
    setSaving(true);
    try {
      const result = await createToken({
        name: form.name,
        expires_at: form.expires_at ? new Date(form.expires_at).toISOString() : null,
        rate_limit_override:
          form.rateLimitMode === "default"
            ? null
            : form.rateLimitMode === "unlimited"
              ? 0
              : Number(form.rateLimitValue),
        allow_plugin_dispatch: form.allow_plugin_dispatch,
        allow_email_alerts: form.allow_email_alerts,
      });
      setCreated(result);
      setCreating(false);
      setShowRaw(false);
      await mutate();
      toast.success(t('toastCreated'));
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('toastFailedCreate'));
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (tObj: AccessTokenOut) => {
    try {
      await updateToken(tObj.id, { is_active: !tObj.is_active });
      toast.success(tObj.is_active ? t('toastDeactivated') : t('toastActivated'));
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('toastFailedUpdate'));
    }
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deleteToken(pendingDelete.id);
      toast.success(t('toastDeleted'));
      setPendingDelete(null);
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('toastFailedDelete'));
    }
  };

  const openEdit = (t: AccessTokenOut) => {
    setEditing(t);
    setEditForm({
      name: t.name,
      rateLimitMode: rateLimitToMode(t.rate_limit_override),
      rateLimitValue: t.rate_limit_override && t.rate_limit_override > 0 ? String(t.rate_limit_override) : "",
      allow_plugin_dispatch: t.allow_plugin_dispatch,
      allow_email_alerts: t.allow_email_alerts,
    });
  };

  const handleSaveEdit = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const params: {
        name?: string;
        rate_limit_override?: number;
        clear_rate_limit_override?: boolean;
        allow_plugin_dispatch?: boolean;
        allow_email_alerts?: boolean;
      } = {};
      if (editForm.name !== editing.name) params.name = editForm.name;
      if (editForm.rateLimitMode === "default") {
        if (editing.rate_limit_override !== null) params.clear_rate_limit_override = true;
      } else if (editForm.rateLimitMode === "unlimited") {
        if (editing.rate_limit_override !== 0) params.rate_limit_override = 0;
      } else {
        const value = Number(editForm.rateLimitValue);
        if (editing.rate_limit_override !== value) params.rate_limit_override = value;
      }
      if (editForm.allow_plugin_dispatch !== editing.allow_plugin_dispatch)
        params.allow_plugin_dispatch = editForm.allow_plugin_dispatch;
      if (editForm.allow_email_alerts !== editing.allow_email_alerts)
        params.allow_email_alerts = editForm.allow_email_alerts;
      if (Object.keys(params).length > 0) {
        await updateToken(editing.id, params);
        toast.success(t('toastUpdated'));
        await mutate();
      }
      setEditing(null);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('toastFailedUpdate'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">
            {tokens?.length ?? 0} {tokens?.length === 1 ? t('tokenCount') : t('tokensCount')}
          </p>
          <p className="text-[11px] text-muted-foreground/60 mt-0.5">
            {t('description')}
          </p>
        </div>
        <Button size="sm" className="h-8 gap-1.5 text-xs" onClick={() => { setCreating(true); setForm({ name: "", expires_at: "", rateLimitMode: "default", rateLimitValue: "", allow_plugin_dispatch: true, allow_email_alerts: true }); }}>
          <Plus className="h-3.5 w-3.5" />
          {t('createToken')}
        </Button>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b border-border">
            <tr>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colName')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colOwner')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colStatus')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colRateLimit')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colExpires')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colLastUsed')}</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 3 }).map((_, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <Skeleton className="h-3 w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              : tokens?.map((tObj) => {
                  const status = tokenStatus(tObj);
                  return (
                    <tr key={tObj.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 text-xs font-medium text-foreground">
                        <span className="flex items-center gap-1.5">
                          {tObj.name}
                          {tObj.is_global
                            ? <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4 bg-cyan-500/15 text-cyan-700 dark:text-cyan-400 border-cyan-500/25">{t('global')}</Badge>
                            : <Badge variant="outline" className="text-[10px] py-0 px-1.5 h-4 bg-violet-500/15 text-violet-700 dark:text-violet-400 border-violet-500/25">{t('private')}</Badge>}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{tObj.owner_username ?? "—"}</td>
                      <td className="px-4 py-3">
                        <Badge variant={status.variant} className="text-[11px]">{t(status.label as any)}</Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground font-mono whitespace-nowrap">
                        {formatRateLimit(tObj.rate_limit_override)}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground font-mono whitespace-nowrap">
                        {tObj.expires_at ? format(new Date(tObj.expires_at), "MMM d, yyyy") : <span className="text-muted-foreground/50">{t('never')}</span>}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground font-mono whitespace-nowrap">
                        {tObj.last_used_at ? format(new Date(tObj.last_used_at), "MMM d, HH:mm") : <span className="text-muted-foreground/50">{t('never')}</span>}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1 justify-end">
                          <TokenTestDialog
                            trigger={
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                                title={t('testToken')}
                              >
                                <span className="text-xs font-mono font-bold">{"{}"}</span>
                              </Button>
                            }
                          />
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                            onClick={() => openEdit(tObj)}
                            title={t('edit')}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                            onClick={() => handleToggle(tObj)}
                            title={tObj.is_active ? t('deactivate') : t('activate')}
                          >
                            {tObj.is_active ? <ToggleRight className="h-3.5 w-3.5" /> : <ToggleLeft className="h-3.5 w-3.5" />}
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                            onClick={() => setPendingDelete(tObj)}
                            title={t('delete')}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>

      {/* Create token dialog */}
      <Dialog open={creating} onOpenChange={(o) => !o && setCreating(false)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">{t('createTitle')}</DialogTitle>
            <DialogDescription className="text-xs">
              {t('createDesc')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label className="text-xs" htmlFor="create-token-name">{t('tokenName')}</Label>
              <Input
                id="create-token-name"
                name="create-token-name"
                className="h-8 text-xs"
                placeholder={t('namePlaceholder')}
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs" htmlFor="create-token-expires-at">{t('expires')} <span className="text-muted-foreground">{t('optional')}</span></Label>
              <Input
                id="create-token-expires-at"
                name="create-token-expires-at"
                className="h-8 text-xs"
                type="datetime-local"
                value={form.expires_at}
                onChange={(e) => setForm({ ...form, expires_at: e.target.value })}
              />
              <p className="text-[11px] text-muted-foreground">{t('leaveBlank')}</p>
            </div>
            <RateLimitFields
              mode={form.rateLimitMode}
              onModeChange={(mode) => setForm({ ...form, rateLimitMode: mode })}
              value={form.rateLimitValue}
              onValueChange={(value) => setForm({ ...form, rateLimitValue: value })}
              idPrefix="create"
            />
            <TokenDeliveryToggles
              idPrefix="create"
              value={{
                allow_plugin_dispatch: form.allow_plugin_dispatch,
                allow_email_alerts: form.allow_email_alerts,
              }}
              onChange={(v) => setForm({ ...form, ...v })}
            />
          </div>
          <DialogFooter>
            <Button size="sm" variant="secondary" onClick={() => setCreating(false)}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              {t('cancel')}
            </Button>
            <Button size="sm" onClick={handleCreate} disabled={saving || !form.name}>
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <Save className="h-3.5 w-3.5 mr-1.5" />}
              {t('createBtn')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reveal token dialog */}
      <Dialog open={!!created} onOpenChange={(o) => !o && setCreated(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-sm">{t('createdTitle')}</DialogTitle>
            <DialogDescription className="text-xs text-amber-700 dark:text-amber-400">
              {t('createdDesc')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label className="text-xs text-muted-foreground">{t('rawToken')}</Label>
              <div className="flex gap-2 items-center">
                <div className="flex-1 rounded-md bg-muted border border-border px-3 py-2 font-mono text-xs text-foreground break-all">
                  {showRaw ? created?.raw_token : "•".repeat(48)}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowRaw((s) => !s)}
                >
                  {showRaw ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </Button>
                {created && <CopyButton value={created.raw_token} />}
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground">
              {t('usageDesc')}
            </p>
          </div>
          <DialogFooter className="sm:justify-between">
            {created && (
              <TokenTestDialog
                token={created.raw_token}
                trigger={
                  <Button size="sm" variant="outline" className="gap-1.5">
                    <span className="text-xs font-mono font-bold">{"{}"}</span>
                    {t('testToken')}
                  </Button>
                }
              />
            )}
            <Button size="sm" onClick={() => setCreated(null)}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              {t('done')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit token dialog */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">{t('editTitle')}</DialogTitle>
            <DialogDescription className="text-xs">
              {t('editDesc')}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label className="text-xs" htmlFor="edit-token-name">{t('tokenName')}</Label>
              <Input
                id="edit-token-name"
                name="edit-token-name"
                className="h-8 text-xs"
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
              />
            </div>
            <RateLimitFields
              mode={editForm.rateLimitMode}
              onModeChange={(mode) => setEditForm({ ...editForm, rateLimitMode: mode })}
              value={editForm.rateLimitValue}
              onValueChange={(value) => setEditForm({ ...editForm, rateLimitValue: value })}
              idPrefix="edit"
            />
            <TokenDeliveryToggles
              idPrefix="edit"
              value={{
                allow_plugin_dispatch: editForm.allow_plugin_dispatch,
                allow_email_alerts: editForm.allow_email_alerts,
              }}
              onChange={(v) => setEditForm({ ...editForm, ...v })}
            />
          </div>
          <DialogFooter>
            <Button size="sm" variant="secondary" onClick={() => setEditing(null)}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              {t('cancel')}
            </Button>
            <Button size="sm" onClick={handleSaveEdit} disabled={saving || !editForm.name}>
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" /> : <Save className="h-3.5 w-3.5 mr-1.5" />}
              {t('save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-sm">{t('deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="text-xs">
              {t('deleteDesc', { name: pendingDelete?.name || "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-8 text-xs">{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              className="h-8 text-xs bg-destructive text-destructive-foreground hover:bg-destructive/90 dark:bg-destructive/60"
              onClick={handleDelete}
            >
              {t('delete')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
