"use client";

import { X, Clock, Wifi, Tag, MessageSquare, Hash, Braces, Eye, CheckCircle2, RotateCcw } from "lucide-react";
import type { NotificationOut } from "@/lib/types";
import type { LabelRule } from "@/lib/use-label-rules";
import { LABEL_COLOR_CLASSES } from "@/lib/use-label-rules";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import { updateNotificationState } from "@/lib/api";
import { useTranslations } from "next-intl";

interface Props {
  notification: NotificationOut;
  tags: string[];
  rules: LabelRule[];
  formatTimestamp: (iso: string) => string;
  onClose: () => void;
  onUpdate: (n: NotificationOut) => void;
  alertStatesEnabled: boolean;
}

interface ContentProps {
  notification: NotificationOut;
  tags: string[];
  rules: LabelRule[];
  formatTimestamp: (iso: string) => string;
  onUpdate: (n: NotificationOut) => void;
  alertStatesEnabled: boolean;
}

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3">
      <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="text-[11px] text-muted-foreground mb-0.5">{label}</p>
        <div className="text-sm text-foreground">{value}</div>
      </div>
    </div>
  );
}

export function NotificationDetailContent({ notification: n, tags, rules, formatTimestamp, onUpdate, alertStatesEnabled }: ContentProps) {
  const t = useTranslations("NotificationDetail");
  const handleStateUpdate = async (newState: "new" | "acknowledged" | "resolved") => {
    try {
      const updated = await updateNotificationState(n.id, newState);
      onUpdate(updated);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-4">
          {/* Title */}
          {n.title && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">{t('title')}</p>
              <p className="text-sm font-medium text-foreground">{n.title}</p>
            </div>
          )}

          <DetailRow
            icon={Clock}
            label={t('receivedAt')}
            value={
              <span className="font-mono text-xs">
                {formatTimestamp(n.received_at)}
              </span>
            }
          />

          {n.occurrences > 1 && (
            <DetailRow
              icon={Clock}
              label={t('lastReceivedAt')}
              value={
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs">
                    {formatTimestamp(n.last_received_at)}
                  </span>
                  <Badge variant="secondary" className="text-[10px]">
                    {t('occurrences', { count: n.occurrences })}
                  </Badge>
                </div>
              }
            />
          )}

          <DetailRow
            icon={Tag}
            label={t('severity')}
            value={
              <span
                className={cn(
                  "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold uppercase border",
                  (() => {
                    const colorKey = 
                      n.severity === "critical" ? "red" :
                      n.severity === "error" ? "orange" :
                      n.severity === "warning" ? "yellow" :
                      n.severity === "info" ? "blue" : "slate";
                    const colors = LABEL_COLOR_CLASSES[colorKey as keyof typeof LABEL_COLOR_CLASSES];
                    return `${colors.bg} ${colors.text} ${colors.border}`;
                  })()
                )}
              >
                {n.severity}
              </span>
            }
          />

          {n.sender_name && (
            <DetailRow
              icon={Tag}
              label={t('sender')}
              value={
                <Badge variant="secondary" className="text-xs font-normal">
                  {n.sender_name}
                </Badge>
              }
            />
          )}

          {tags.length > 0 && (
            <DetailRow
              icon={Hash}
              label={t('labels')}
              value={
                <div className="flex flex-wrap gap-1.5 mt-0.5">
                  {tags.map((tag) => {
                    const rule = rules.find((r) => r.name === tag);
                    const colors = rule ? LABEL_COLOR_CLASSES[rule.color] : LABEL_COLOR_CLASSES.slate;
                    return (
                      <span
                        key={tag}
                        className={cn(
                          "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border",
                          colors.bg,
                          colors.text,
                          colors.border
                        )}
                      >
                        {tag}
                      </span>
                    );
                  })}
                </div>
              }
            />
          )}

          {n.tags && n.tags.length > 0 && (
            <DetailRow
              icon={Hash}
              label={t('tags')}
              value={
                <div className="flex flex-wrap gap-1.5 mt-0.5">
                  {n.tags.map((tag) => (
                    <span
                      key={`explicit-${tag}`}
                      className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium border bg-slate-500/10 text-slate-500 border-slate-500/20"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              }
            />
          )}

          {n.source_ip && (
            <DetailRow
              icon={Wifi}
              label={t('sourceIp')}
              value={<span className="font-mono text-xs">{n.source_ip}</span>}
            />
          )}

          {Object.keys(n.custom_fields ?? {}).length > 0 && (
            <>
              <Separator />
              <DetailRow
                icon={Braces}
                label={t('customFields')}
                value={
                  <table className="w-full text-xs border-collapse mt-0.5">
                    <tbody>
                      {Object.entries(n.custom_fields).map(([k, v]) => (
                        <tr key={k} className="border-b border-border last:border-0">
                          <td className="py-1 pr-3 text-muted-foreground font-mono align-top w-2/5 break-all">{k}</td>
                          <td className="py-1 font-mono text-foreground align-top break-all">
                            {typeof v === "object" ? JSON.stringify(v) : String(v)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                }
              />
            </>
          )}

          <Separator />

          <DetailRow
            icon={MessageSquare}
            label={t('message')}
            value={
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed bg-muted rounded-md p-3 text-foreground">
                {n.message}
              </pre>
            }
          />

          <div>
            <p className="text-[11px] text-muted-foreground mb-1">{t('id')}</p>
            <p className="font-mono text-[11px] text-muted-foreground break-all">{n.id}</p>
          </div>

          {alertStatesEnabled && (
            <>
              <Separator />
              <div className="pt-2 flex items-center justify-between">
                <span className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
                  {t('state', { state: n.state })}
                </span>
                <div className="flex gap-2">
                  {n.state !== "acknowledged" && n.state !== "resolved" && (
                    <Button size="sm" variant="secondary" onClick={() => handleStateUpdate("acknowledged")} className="gap-1.5">
                      <Eye className="h-3.5 w-3.5" />
                      {t('acknowledge')}
                    </Button>
                  )}
                  {n.state !== "resolved" && (
                    <Button size="sm" onClick={() => handleStateUpdate("resolved")} className="gap-1.5">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {t('resolve')}
                    </Button>
                  )}
                  {n.state !== "new" && (
                    <Button size="sm" variant="outline" onClick={() => handleStateUpdate("new")} className="gap-1.5">
                      <RotateCcw className="h-3.5 w-3.5" />
                      {t('reset')}
                    </Button>
                  )}
                </div>
              </div>
            </>
          )}
    </div>
  );
}

export function NotificationDetail({ notification, tags, rules, formatTimestamp, onClose, onUpdate, alertStatesEnabled }: Props) {
  const t = useTranslations("NotificationDetail");
  return (
    <div className="hidden lg:flex w-80 xl:w-96 flex-col border-l border-border bg-card shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {t('detailHeader')}
        </span>
        <Button
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
          onClick={onClose}
        >
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="px-4 py-4">
          <NotificationDetailContent
            notification={notification}
            tags={tags}
            rules={rules}
            formatTimestamp={formatTimestamp}
            onUpdate={onUpdate}
            alertStatesEnabled={alertStatesEnabled}
          />
        </div>
      </ScrollArea>
    </div>
  );
}
