"use client";

import { useState } from "react";
import useSWR from "swr";
import { format } from "date-fns";
import { Plus, Pencil, Trash2, UserPlus, ToggleLeft, ToggleRight, Loader2, Save, X } from "lucide-react";
import { toast } from "sonner";
import { fetchUsers, updateUser, deleteUser, createUser } from "@/lib/api";
import type { UserOut } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
import { useTranslations } from "next-intl";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type UserForm = {
  sub: string;
  email: string;
  username: string;
  full_name: string;
  role: "viewer" | "admin";
};

const emptyForm: UserForm = {
  sub: "",
  email: "",
  username: "",
  full_name: "",
  role: "viewer",
};

export function UsersTab() {
  const t = useTranslations("AdminTabs.users");
  const { data: users, isLoading, mutate } = useSWR<UserOut[]>("/admin/users", fetchUsers);
  const [editing, setEditing] = useState<UserOut | null | any>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<UserForm>(emptyForm);
  const [pendingDelete, setPendingDelete] = useState<UserOut | null>(null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    const payload = {
      sub: editing.sub,
      email: editing.email,
      username: editing.username,
      full_name: editing.full_name || undefined,
      role: editing.role,
    };
    try {
      if (editing?.id) {
        await updateUser(editing.id, payload);
        toast.success(t('toastUpdated'));
      } else {
        await createUser(payload);
        toast.success(t('toastCreated'));
      }
      setEditing(null);
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('toastFailedSave'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deleteUser(pendingDelete.id);
      toast.success(t('toastDeleted'));
      setPendingDelete(null);
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('toastFailedDelete'));
    }
  };

  const handleToggle = async (u: UserOut) => {
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      toast.success(u.is_active ? t('toastDeactivated') : t('toastActivated'));
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : t('toastFailedUpdate'));
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">
            {users?.length ?? 0} {users?.length === 1 ? t('userCount') : t('usersCount')}
          </p>
        </div>
        <Button size="sm" className="h-8 gap-1.5 text-xs" onClick={() => setEditing({})}>
          <UserPlus className="h-3.5 w-3.5" />
          {t('addUser')}
        </Button>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b border-border">
            <tr>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colUsername')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colEmail')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colRole')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colStatus')}</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">{t('colCreated')}</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="border-b border-border last:border-0">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <Skeleton className="h-3 w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              : users?.map((u) => (
                  <tr key={u.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-foreground text-xs">{u.username}</p>
                      {u.full_name && (
                        <p className="text-[11px] text-muted-foreground">{u.full_name}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{u.email}</td>
                    <td className="px-4 py-3">
                      <Badge
                        variant={u.role === "admin" ? "default" : "secondary"}
                        className="text-[11px] capitalize"
                      >
                        {u.role}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active
                        ? <Badge variant="outline" className="text-[11px]">{t('active')}</Badge>
                        : <Badge variant="destructive" className="text-[11px]">{t('inactive')}</Badge>}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground font-mono whitespace-nowrap">
                      {format(new Date(u.created_at), "MMM d, yyyy")}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 justify-end">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                          onClick={() => handleToggle(u)}
                          title={u.is_active ? t('deactivate') : t('activate')}
                        >
                          {u.is_active ? <ToggleRight className="h-3.5 w-3.5" /> : <ToggleLeft className="h-3.5 w-3.5" />}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                          onClick={() => setEditing(u)}
                          title={t('edit')}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                          onClick={() => setPendingDelete(u)}
                          title={t('delete')}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      <Dialog
        open={!!editing}
        onOpenChange={(open) => {
          if (!open) {
            setEditing(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">
              {editing?.id ? t('editTitle') : t('createTitle')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label className="text-xs" htmlFor="edit-user-sub">{t('sub')}</Label>
              <Input
                id="edit-user-sub"
                className="h-8 text-xs"
                placeholder={t('subPlaceholder')}
                value={editing?.sub || ""}
                onChange={(e) => setEditing({ ...editing, sub: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs" htmlFor="edit-user-username">{t('username')}</Label>
                <Input
                  id="edit-user-username"
                  className="h-8 text-xs"
                  value={editing?.username || ""}
                  onChange={(e) => setEditing({ ...editing, username: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs" htmlFor="edit-user-name">{t('fullName')}</Label>
                <Input
                  id="edit-user-name"
                  className="h-8 text-xs"
                  value={editing?.full_name || ""}
                  onChange={(e) => setEditing({ ...editing, full_name: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs" htmlFor="edit-user-email">{t('email')}</Label>
              <Input
                id="edit-user-email"
                type="email"
                className="h-8 text-xs"
                value={editing?.email || ""}
                onChange={(e) => setEditing({ ...editing, email: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">{t('role')}</Label>
              <Select
                value={editing?.role || "viewer"}
                onValueChange={(v) => setEditing({ ...editing, role: v })}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">{t('viewer')}</SelectItem>
                  <SelectItem value="admin">{t('admin')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button size="sm" variant="secondary" onClick={() => setEditing(null)}>
              <X className="h-3.5 w-3.5 mr-1.5" />
              {t('cancel')}
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving || !editing?.sub || !editing?.username} className="gap-1.5">
              {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
              {editing?.id ? t('save') : t('createBtn')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-sm">{t('deleteTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="text-xs">
              {t('deleteDesc', { username: pendingDelete?.username || "" })}
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
