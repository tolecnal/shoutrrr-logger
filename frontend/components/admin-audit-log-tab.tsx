"use client";

import { useState } from "react";
import useSWR from "swr";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { fetchAuditLogs, auditLogsKey } from "@/lib/api";
import type { AuditLogOut } from "@/lib/types";
import { usePreferences } from "@/lib/use-preferences";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const AUDIT_ACTIONS = [
  "user.create",
  "user.update",
  "user.delete",
  "token.create",
  "token.update",
  "token.delete",
  "settings.update",
  "plugin.update",
] as const;

const PAGE_SIZE = 20;

function actionBadgeClass(action: string): string {
  if (action.endsWith(".create")) return "bg-emerald-500/15 text-emerald-400 border-emerald-500/25";
  if (action.endsWith(".update")) return "bg-amber-500/15 text-amber-400 border-amber-500/25";
  if (action.endsWith(".delete")) return "bg-red-500/15 text-red-400 border-red-500/25";
  return "bg-muted text-muted-foreground border-border";
}

function targetLabel(entry: AuditLogOut): string {
  return entry.target_id ? `${entry.target_type}/${entry.target_id}` : entry.target_type;
}

export function AuditLogTab() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState<string | undefined>(undefined);
  const [details, setDetails] = useState<AuditLogOut | null>(null);

  const { formatTimestamp } = usePreferences();

  const { data, isLoading } = useSWR(auditLogsKey(page, PAGE_SIZE, action), fetchAuditLogs);

  const handleActionChange = (value: string) => {
    setAction(value === "__all" ? undefined : value);
    setPage(1);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-muted-foreground">
            {data?.total ?? 0} entr{data?.total === 1 ? "y" : "ies"}
          </p>
          <p className="text-[11px] text-muted-foreground/60 mt-0.5">
            Records of admin actions: user, token, settings, and plugin changes.
          </p>
        </div>
        <Select value={action ?? "__all"} onValueChange={handleActionChange}>
          <SelectTrigger className="h-8 w-44 text-xs">
            <SelectValue placeholder="All actions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all">All actions</SelectItem>
            {AUDIT_ACTIONS.map((a) => (
              <SelectItem key={a} value={a}>{a}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 border-b border-border">
            <tr>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Time</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Actor</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Action</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">Target</th>
              <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2.5">IP</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-border last:border-0">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3">
                      <Skeleton className="h-3 w-20" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data?.items.length ? (
              data.items.map((entry) => (
                <tr key={entry.id} className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3 text-xs text-muted-foreground font-mono whitespace-nowrap">
                    {formatTimestamp(entry.created_at)}
                  </td>
                  <td className="px-4 py-3 text-xs text-foreground">
                    {entry.actor_username ?? <span className="text-muted-foreground/50">—</span>}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant="outline" className={`text-[10px] py-0 px-1.5 h-4 font-mono ${actionBadgeClass(entry.action)}`}>
                      {entry.action}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground font-mono">
                    {targetLabel(entry)}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground font-mono">
                    {entry.ip_address ?? <span className="text-muted-foreground/50">—</span>}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {entry.details && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                        onClick={() => setDetails(entry)}
                      >
                        Details
                      </Button>
                    )}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-xs text-muted-foreground">
                  No audit log entries yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {data && data.pages > 1 && (
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Page {data.page} of {data.pages}</span>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0"
              disabled={page >= data.pages}
              onClick={() => setPage((p) => p + 1)}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}

      <Dialog open={!!details} onOpenChange={(o) => !o && setDetails(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="text-sm">Audit Log Details</DialogTitle>
          </DialogHeader>
          <pre className="text-xs bg-muted rounded-md p-3 overflow-auto max-h-96 whitespace-pre-wrap break-all">
            {details ? JSON.stringify(details.details, null, 2) : ""}
          </pre>
        </DialogContent>
      </Dialog>
    </div>
  );
}
