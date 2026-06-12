"use client";

import { useState } from "react";
import useSWR from "swr";
import { format } from "date-fns";
import { Plus, Pencil, Trash2, UserCheck, UserX, Loader2 } from "lucide-react";
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
  const { data: users, isLoading, mutate } = useSWR("/admin/users", fetchUsers);
  const [editing, setEditing] = useState<UserOut | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<UserForm>(emptyForm);
  const [pendingDelete, setPendingDelete] = useState<UserOut | null>(null);
  const [saving, setSaving] = useState(false);

  const openEdit = (u: UserOut) => {
    setEditing(u);
    setForm({
      sub: u.sub,
      email: u.email,
      username: u.username,
      full_name: u.full_name ?? "",
      role: u.role,
    });
  };

  const openCreate = () => {
    setCreating(true);
    setForm(emptyForm);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await updateUser(editing.id, {
          email: form.email,
          username: form.username,
          full_name: form.full_name || undefined,
          role: form.role,
        });
        toast.success("User updated.");
        setEditing(null);
      } else {
        await createUser({
          sub: form.sub,
          email: form.email,
          username: form.username,
          full_name: form.full_name || undefined,
          role: form.role,
        });
        toast.success("User created.");
        setCreating(false);
      }
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to save user.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deleteUser(pendingDelete.id);
      toast.success("User deleted.");
      setPendingDelete(null);
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to delete user.");
    }
  };

  const handleToggleActive = async (u: UserOut) => {
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      toast.success(u.is_active ? "User deactivated." : "User activated.");
      await mutate();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to update user.");
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          {users?.length ?? 0} user{users?.length !== 1 ? "s" : ""}
        </p>
        <Button size="sm" className="h-8 gap-1.5 text-xs" onClick={openCreate}>
          <Plus className="h-3.5 w-3.5" />
          Add User
        </Button>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b border-border">
            <tr>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Username</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Email</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Role</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Status</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Created</th>
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
                      <Badge
                        variant={u.is_active ? "outline" : "destructive"}
                        className="text-[11px]"
                      >
                        {u.is_active ? "Active" : "Inactive"}
                      </Badge>
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
                          onClick={() => handleToggleActive(u)}
                          title={u.is_active ? "Deactivate" : "Activate"}
                        >
                          {u.is_active ? <UserX className="h-3.5 w-3.5" /> : <UserCheck className="h-3.5 w-3.5" />}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                          onClick={() => openEdit(u)}
                          title="Edit"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                          onClick={() => setPendingDelete(u)}
                          title="Delete"
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

      {/* Edit / Create dialog */}
      <Dialog
        open={!!editing || creating}
        onOpenChange={(open) => {
          if (!open) {
            setEditing(null);
            setCreating(false);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">{editing ? "Edit User" : "Add User"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {!editing && (
              <div className="space-y-1">
                <Label className="text-xs" htmlFor="user-sub">OIDC Subject (sub)</Label>
                <Input
                  id="user-sub"
                  name="user-sub"
                  className="h-8 text-xs"
                  value={form.sub}
                  onChange={(e) => setForm({ ...form, sub: e.target.value })}
                  placeholder="e.g. keycloak-user-uuid"
                />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs" htmlFor="user-username">Username</Label>
                <Input
                  id="user-username"
                  name="user-username"
                  className="h-8 text-xs"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs" htmlFor="user-full-name">Full name</Label>
                <Input
                  id="user-full-name"
                  name="user-full-name"
                  className="h-8 text-xs"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs" htmlFor="user-email">Email</Label>
              <Input
                id="user-email"
                name="user-email"
                className="h-8 text-xs"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Role</Label>
              <Select
                value={form.role}
                onValueChange={(v) => setForm({ ...form, role: v as "viewer" | "admin" })}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer" className="text-xs">Viewer</SelectItem>
                  <SelectItem value="admin" className="text-xs">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => { setEditing(null); setCreating(false); }}
            >
              Cancel
            </Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />}
              {editing ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="text-sm">Delete user?</AlertDialogTitle>
            <AlertDialogDescription className="text-xs">
              This will permanently delete <strong>{pendingDelete?.username}</strong> and all their access tokens.
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="h-8 text-xs">Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="h-8 text-xs bg-destructive text-destructive-foreground hover:bg-destructive/90 dark:bg-destructive/60"
              onClick={handleDelete}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
