"use client";

import { useCallback, useEffect, useState } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { ArrowRight, Bell, CheckCircle2, Circle, Trash2, Inbox } from "lucide-react";
import { fetchAlerts, updateAlertState, deleteAlert, deleteAlerts } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { usePreferences } from "@/lib/use-preferences";
import { NotificationDetailContent } from "@/components/notification-detail";
import { useTranslations } from "next-intl";

export function AlertsPage() {
  const t = useTranslations("Alerts");
  const { data: alerts, mutate, isLoading } = useSWR("/alerts", fetchAlerts, { refreshInterval: 10000 });
  const [updating, setUpdating] = useState<Record<string, boolean>>({});
  const { formatTimestamp } = usePreferences();
  const [selectedAlertId, setSelectedAlertId] = useState<string | null>(null);

  const handleToggleState = useCallback(async (id: string, currentStateIsRead: boolean) => {
    setUpdating(prev => ({ ...prev, [id]: true }));
    try {
      await updateAlertState([id], !currentStateIsRead);
      await mutate();
    } finally {
      setUpdating(prev => ({ ...prev, [id]: false }));
    }
  }, [mutate]);

  // Move to the next unread alert (in displayed order), or close the dialog
  // if there are no more unread alerts.
  const goToNextUnread = useCallback(() => {
    if (!selectedAlertId || !alerts) return;
    const sorted = [...alerts].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    const idx = sorted.findIndex(a => a.id === selectedAlertId);
    if (idx === -1) return;
    const next = sorted.slice(idx + 1).find(a => !a.is_read);
    setSelectedAlertId(next ? next.id : null);
  }, [alerts, selectedAlertId]);

  // Keyboard shortcuts while the alert dialog is open: "r" toggles
  // read/unread, "n" jumps to the next unread alert.
  useEffect(() => {
    if (!selectedAlertId) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const key = e.key.toLowerCase();
      if (key === "r") {
        const alert = alerts?.find(a => a.id === selectedAlertId);
        if (!alert) return;
        e.preventDefault();
        handleToggleState(alert.id, alert.is_read);
      } else if (key === "n") {
        e.preventDefault();
        goToNextUnread();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedAlertId, alerts, handleToggleState, goToNextUnread]);

  const handleDelete = async (id: string) => {
    setUpdating(prev => ({ ...prev, [id]: true }));
    try {
      await deleteAlert(id);
      await mutate();
    } finally {
      setUpdating(prev => ({ ...prev, [id]: false }));
    }
  };

  const markAllRead = async () => {
    if (!alerts) return;
    try {
      await updateAlertState([], true, true);
      await mutate();
    } catch (e) {
      console.error(e);
    }
  };

  const sortedAlerts = [...(alerts || [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  const selectedAlert = alerts?.find(a => a.id === selectedAlertId);

  return (
    <div className="flex h-full flex-col bg-background relative">
      <div className="flex flex-col flex-1 min-h-0 min-w-0">
        {/* Header bar */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-card">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-foreground" />
            <h1 className="text-sm font-semibold tracking-tight text-foreground">{t('title')}</h1>
            {alerts && (
              <span className="text-xs text-muted-foreground ml-2">
                {alerts.length} {t('total')} • {alerts.filter(a => !a.is_read).length} {t('unread')}
              </span>
            )}
          </div>
          <Button onClick={markAllRead} variant="outline" size="sm" disabled={!alerts?.some(a => !a.is_read)}>
            <CheckCircle2 className="mr-2 h-4 w-4" />
            {t('markAllAsRead')}
          </Button>
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          {isLoading && !alerts ? (
            <div className="space-y-px">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-border">
                  <Skeleton className="h-3 w-24 shrink-0" />
                  <Skeleton className="h-3 flex-1" />
                  <Skeleton className="h-3 w-16 shrink-0" />
                </div>
              ))}
            </div>
          ) : sortedAlerts.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
              <Inbox className="h-8 w-8 text-muted-foreground/50" />
              <h3 className="text-sm font-medium text-foreground">{t('noAlerts')}</h3>
              <p className="text-sm text-muted-foreground mt-1">
                {t('noAlertsDescription')}
              </p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-card/90 backdrop-blur-sm border-b border-border">
                <tr>
                  <th className="text-center px-4 py-2 w-12">
                    <span className="sr-only">{t('colStatus')}</span>
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-44">
                    {t('colTriggered')}
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-24">
                    {t('colSeverity')}
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-48">
                    {t('colSender')}
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2">
                    {t('colMessage')}
                  </th>
                  <th className="text-right text-xs text-muted-foreground font-medium px-4 py-2 w-24">
                    {t('colActions')}
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedAlerts.map((alert) => {
                  const n = alert.notification;
                  const isSelected = selectedAlertId === alert.id;
                  const severityColors: Record<string, string> = {
                    critical: "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/25",
                    error: "bg-orange-500/15 text-orange-700 dark:text-orange-400 border-orange-500/25",
                    warning: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/25",
                    info: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/25",
                    debug: "bg-zinc-500/15 text-zinc-700 dark:text-zinc-400 border-zinc-500/25",
                  };
                  const sevColor = n?.severity ? severityColors[n.severity.toLowerCase()] || severityColors.info : severityColors.info;
                  
                  return (
                    <tr
                      key={alert.id}
                      onClick={() => setSelectedAlertId(isSelected ? null : alert.id)}
                      className={cn(
                        "group border-b border-border cursor-pointer transition-colors",
                        !alert.is_read ? "bg-accent/20" : "bg-card",
                        isSelected && "bg-muted/60",
                        updating[alert.id] && "opacity-50 pointer-events-none"
                      )}
                    >
                      <td className="px-4 py-2 align-top pt-3 text-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleToggleState(alert.id, alert.is_read);
                          }}
                          className="text-muted-foreground hover:text-foreground transition-colors"
                          title={!alert.is_read ? t('markAsRead') : t('markAsUnread')}
                        >
                          {!alert.is_read ? (
                            <Circle className="h-4 w-4 fill-blue-500/20 text-blue-500" />
                          ) : (
                            <CheckCircle2 className="h-4 w-4 opacity-50" />
                          )}
                        </button>
                      </td>
                      <td className="px-4 py-2 align-top pt-3 whitespace-nowrap text-xs text-muted-foreground">
                        {formatTimestamp(alert.created_at)}
                      </td>
                      <td className="px-4 py-2 align-top pt-2">
                        {n?.severity ? (
                          <span className={cn("inline-flex items-center px-1.5 py-0.5 rounded-[4px] text-[10px] font-semibold tracking-wide uppercase border", sevColor)}>
                            {n.severity}
                          </span>
                        ) : (
                          <span className="text-muted-foreground/50 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-2 align-top pt-3">
                        <span className={cn("font-medium", !alert.is_read ? "text-foreground" : "text-foreground/80")}>
                          {n?.sender_name || t('unknown')}
                        </span>
                      </td>
                      <td className="px-4 py-2 align-top pt-3">
                        <div className="flex flex-col gap-0.5">
                          {n?.title && (
                            <span className={cn("font-medium", !alert.is_read ? "text-foreground" : "text-foreground/80")}>
                              {n.title}
                            </span>
                          )}
                          <span className={cn("line-clamp-2 text-muted-foreground", !n?.title && "mt-0")}>
                            {n?.message || t('noContent')}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-2 align-top pt-2 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(alert.id);
                          }}
                          className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          <span className="sr-only">{t('deleteAlert')}</span>
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
      <Dialog open={!!selectedAlert} onOpenChange={(open) => !open && setSelectedAlertId(null)}>
        <DialogContent className="flex max-h-[85vh] flex-col sm:max-w-xl">
          {selectedAlert && selectedAlert.notification && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-6">
                  {selectedAlert.notification.title || selectedAlert.notification.sender_name || t('alertDetails')}
                </DialogTitle>
                <DialogDescription className="sr-only">
                  {t('alertDetailsDescription')}
                </DialogDescription>
              </DialogHeader>
              <ScrollArea className="flex-1 -mx-6 px-6">
                <NotificationDetailContent
                  notification={selectedAlert.notification}
                  tags={[]}
                  rules={[]}
                  formatTimestamp={formatTimestamp}
                  onUpdate={() => {}}
                  alertStatesEnabled={false}
                />
              </ScrollArea>
              <DialogFooter>
                <Button
                  variant={selectedAlert.is_read ? "outline" : "default"}
                  onClick={() => handleToggleState(selectedAlert.id, selectedAlert.is_read)}
                >
                  {selectedAlert.is_read ? (
                    <Circle className="mr-2 h-4 w-4" />
                  ) : (
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                  )}
                  {selectedAlert.is_read ? t('markAsUnread') : t('markAsRead')}
                  <kbd className="ml-2 hidden h-5 items-center rounded border border-border/60 bg-muted px-1.5 font-mono text-[10px] text-muted-foreground sm:inline-flex">
                    R
                  </kbd>
                </Button>
                <Button variant="secondary" onClick={goToNextUnread}>
                  {t('nextUnread')}
                  <ArrowRight className="ml-2 h-4 w-4" />
                  <kbd className="ml-2 hidden h-5 items-center rounded border border-border/60 bg-muted px-1.5 font-mono text-[10px] text-muted-foreground sm:inline-flex">
                    N
                  </kbd>
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
