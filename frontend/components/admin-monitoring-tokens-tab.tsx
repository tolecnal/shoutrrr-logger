"use client";

import { useState } from "react";
import useSWR from "swr";
import { format } from "date-fns";
import { Plus, Trash2, ToggleLeft, ToggleRight, Loader2, Save, X, Pencil } from "lucide-react";
import { toast } from "sonner";
import { fetchMonitoringTokens, createMonitoringToken, deleteMonitoringToken, updateMonitoringToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CopyButton } from "@/components/copy-button";
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
import { MonitoringTokenTestDialog } from "@/components/monitoring-token-test-dialog";
import { useTranslations } from "next-intl";

export function MonitoringTokensTab() {
  const t = useTranslations("AdminTabs.monitoring");
  const { data: tokens, error, isLoading, mutate } = useSWR("/admin/monitoring-tokens", fetchMonitoringTokens);

  // New token dialog state
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Newly created token state
  const [createdToken, setCreatedToken] = useState<any | null>(null);

  // Delete token state
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Edit token state
  const [editToken, setEditToken] = useState<any | null>(null);
  const [editName, setEditName] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);

  const [toggling, setToggling] = useState<string | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const res = await createMonitoringToken({
        name: newName.trim(),
      });
      setCreatedToken(res);
      setNewName("");
      setIsAddOpen(false);
      mutate();
      toast.success(t('toastCreated'));
    } catch (err: any) {
      toast.error(err.message || t('toastFailedCreate'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async (token: any) => {
    if (toggling) return;
    setToggling(token.id);
    try {
      await updateMonitoringToken(token.id, { is_active: !token.is_active });
      mutate();
    } catch (err: any) {
      toast.error(err.message || t('toastFailedToggle'));
    } finally {
      setToggling(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteId || isDeleting) return;
    setIsDeleting(true);
    try {
      await deleteMonitoringToken(deleteId);
      mutate();
      setDeleteId(null);
      toast.success(t('toastDeleted'));
    } catch (err: any) {
      toast.error(err.message || t('toastFailedDelete'));
    } finally {
      setIsDeleting(false);
    }
  };

  const openEdit = (token: any) => {
    setEditToken(token);
    setEditName(token.name);
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editToken || !editName.trim() || isUpdating) return;
    setIsUpdating(true);
    try {
      await updateMonitoringToken(editToken.id, {
        name: editName.trim(),
      });
      setEditToken(null);
      mutate();
      toast.success(t('toastUpdated'));
    } catch (err: any) {
      toast.error(err.message || t('toastFailedUpdate'));
    } finally {
      setIsUpdating(false);
    }
  };

  if (error) {
    return <div className="text-sm text-destructive px-2 py-4">Failed to load monitoring tokens: {error.message}</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground max-w-[600px]">
          {t('description')}
        </div>
        <Button size="sm" onClick={() => setIsAddOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          {t('createToken')}
        </Button>
      </div>

      <div className="border border-border rounded-md divide-y divide-border bg-card">
        {isLoading ? (
          <div className="p-4 space-y-3">
            <Skeleton className="h-4 w-[200px]" />
            <Skeleton className="h-4 w-[150px]" />
          </div>
        ) : !tokens?.length ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            {t('noTokens')}
          </div>
        ) : (
          tokens.map((token) => (
            <div key={token.id} className="p-3 flex items-center justify-between hover:bg-muted/50 transition-colors">
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-sm truncate">{token.name}</span>
                  {!token.is_active && <Badge variant="secondary" className="text-[10px]">{t('inactive')}</Badge>}
                </div>
                <div className="text-xs text-muted-foreground flex items-center gap-3">
                  <span>{t('created')} {format(new Date(token.created_at), "MMM d, yyyy HH:mm")}</span>
                  <span>{t('lastUsed')} {token.last_used_at ? format(new Date(token.last_used_at), "MMM d, yyyy HH:mm") : t('never')}</span>
                </div>
              </div>

              <div className="flex items-center gap-1 ml-4 shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 px-2 text-muted-foreground hover:text-foreground"
                  onClick={() => handleToggleActive(token)}
                  disabled={toggling === token.id}
                  title={token.is_active ? t('deactivate') : t('activate')}
                >
                  {toggling === token.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : token.is_active ? (
                    <ToggleRight className="h-5 w-5 text-green-500" />
                  ) : (
                    <ToggleLeft className="h-5 w-5" />
                  )}
                </Button>

                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 text-muted-foreground"
                  onClick={() => openEdit(token)}
                  title={t('edit')}
                >
                  <Pencil className="h-4 w-4" />
                </Button>

                <MonitoringTokenTestDialog
                  trigger={
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                      title={t('test')}
                    >
                      <span className="text-xs font-mono font-bold">{"{}"}</span>
                    </Button>
                  }
                />

                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => setDeleteId(token.id)}
                  title={t('delete')}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* CREATE DIALOG */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle>{t('createTitle')}</DialogTitle>
              <DialogDescription>
                {t('createDesc')}
              </DialogDescription>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="token-name">{t('name')}</Label>
                <Input
                  id="token-name"
                  placeholder={t('namePlaceholder')}
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  autoFocus
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={!newName.trim() || isSubmitting}>
                {isSubmitting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                {t('createBtn')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* CREATED DIALOG */}
      <Dialog open={!!createdToken} onOpenChange={(o) => !o && setCreatedToken(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{t('createdTitle')}</DialogTitle>
            <DialogDescription className="text-amber-600 dark:text-amber-400 font-medium">
              {t('createdDesc')}
            </DialogDescription>
          </DialogHeader>
          {createdToken && (
            <div className="py-4 space-y-3">
              <div className="p-3 bg-muted rounded-md font-mono text-sm break-all select-all flex items-start gap-2">
                <div className="flex-1">{createdToken.raw_token}</div>
                <CopyButton value={createdToken.raw_token} className="h-6 w-6" />
              </div>
              <p className="text-xs text-muted-foreground">
                {t('usageDesc')}
              </p>
            </div>
          )}
          <DialogFooter className="flex sm:justify-between items-center w-full">
            <MonitoringTokenTestDialog
              token={createdToken?.raw_token}
              trigger={
                <Button variant="outline">
                  {t('testBtn')}
                </Button>
              }
            />
            <Button onClick={() => setCreatedToken(null)}>
              <X className="h-4 w-4 mr-2" />
              {t('close')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* EDIT DIALOG */}
      <Dialog open={!!editToken} onOpenChange={(o) => !o && setEditToken(null)}>
        <DialogContent className="sm:max-w-[425px]">
          <form onSubmit={handleEdit}>
            <DialogHeader>
              <DialogTitle>{t('editTitle')}</DialogTitle>
            </DialogHeader>
            <div className="py-4 space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="edit-name">{t('name')}</Label>
                <Input
                  id="edit-name"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  autoFocus
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setEditToken(null)}>
                <X className="h-4 w-4 mr-2" />
                {t('cancel')}
              </Button>
              <Button type="submit" disabled={!editName.trim() || isUpdating}>
                {isUpdating ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
                {t('saveChanges')}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* DELETE DIALOG */}
      <AlertDialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t('deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('deleteDesc')}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t('cancel')}</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleDelete();
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isDeleting}
            >
              {isDeleting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              {t('deleteBtn')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
