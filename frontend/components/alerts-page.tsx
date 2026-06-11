"use client";

import { useState } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";
import { Bell, CheckCircle2, Circle, Trash2, ShieldAlert } from "lucide-react";
import { fetchAlerts, updateAlertState, deleteAlert } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function AlertsPage() {
  const { data: alerts, mutate, isLoading } = useSWR("/alerts", fetchAlerts, { refreshInterval: 10000 });
  const [updating, setUpdating] = useState<Record<string, boolean>>({});

  const handleToggleState = async (id: string, currentState: "read" | "unread") => {
    setUpdating(prev => ({ ...prev, [id]: true }));
    try {
      const newState = currentState === "read" ? "unread" : "read";
      await updateAlertState(id, newState);
      await mutate();
    } finally {
      setUpdating(prev => ({ ...prev, [id]: false }));
    }
  };

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
    const unread = alerts.filter(a => a.state === "unread");
    for (const a of unread) {
      setUpdating(prev => ({ ...prev, [a.id]: true }));
      await updateAlertState(a.id, "read");
    }
    await mutate();
  };

  if (isLoading && !alerts) {
    return <div className="p-8 text-center text-muted-foreground">Loading alerts...</div>;
  }

  const sortedAlerts = [...(alerts || [])].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="max-w-4xl mx-auto py-8 px-4 sm:px-6">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Alerts</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Stay on top of critical notifications
          </p>
        </div>
        <Button onClick={markAllRead} variant="outline" size="sm" disabled={!alerts?.some(a => a.state === "unread")}>
          <CheckCircle2 className="mr-2 h-4 w-4" />
          Mark all as read
        </Button>
      </div>

      {sortedAlerts.length === 0 ? (
        <div className="text-center py-16 border rounded-lg border-dashed">
          <ShieldAlert className="h-12 w-12 mx-auto text-muted-foreground mb-4 opacity-50" />
          <h3 className="text-lg font-medium text-foreground">No alerts yet</h3>
          <p className="text-sm text-muted-foreground mt-1">
            When your alert rules match incoming notifications, they'll appear here.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {sortedAlerts.map(alert => (
            <div
              key={alert.id}
              className={cn(
                "flex items-start gap-4 p-4 rounded-lg border transition-colors",
                alert.state === "unread" ? "bg-accent/50 border-accent-foreground/20" : "bg-card border-border",
                updating[alert.id] && "opacity-50 pointer-events-none"
              )}
            >
              <button
                onClick={() => handleToggleState(alert.id, alert.state)}
                className="mt-1 text-muted-foreground hover:text-foreground shrink-0 transition-colors"
                title={alert.state === "unread" ? "Mark as read" : "Mark as unread"}
              >
                {alert.state === "unread" ? (
                  <Circle className="h-5 w-5 fill-blue-500/20 text-blue-500" />
                ) : (
                  <CheckCircle2 className="h-5 w-5" />
                )}
              </button>
              
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-4 mb-1">
                  <h3 className={cn("font-medium truncate", alert.state === "unread" ? "text-foreground" : "text-muted-foreground")}>
                    {alert.title}
                  </h3>
                  <span className="text-xs text-muted-foreground shrink-0">
                    {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                  </span>
                </div>
                <p className={cn("text-sm break-words", alert.state === "unread" ? "text-foreground/90" : "text-muted-foreground")}>
                  {alert.message}
                </p>
                {alert.severity && (
                  <div className="mt-3">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-secondary text-secondary-foreground uppercase">
                      {alert.severity}
                    </span>
                  </div>
                )}
              </div>

              <div className="shrink-0 flex items-center">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDelete(alert.id)}
                  className="h-8 w-8 p-0 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                >
                  <Trash2 className="h-4 w-4" />
                  <span className="sr-only">Delete alert</span>
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
