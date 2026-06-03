"use client";

import { X, Clock, Wifi, Tag, MessageSquare, Hash, Braces } from "lucide-react";
import type { NotificationOut } from "@/lib/types";
import type { TagRule } from "@/lib/use-tag-rules";
import { TAG_COLOR_CLASSES } from "@/lib/use-tag-rules";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";

interface Props {
  notification: NotificationOut;
  tags: string[];
  rules: TagRule[];
  formatTimestamp: (iso: string) => string;
  onClose: () => void;
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

export function NotificationDetail({ notification: n, tags, rules, formatTimestamp, onClose }: Props) {
  return (
    <div className="hidden lg:flex w-80 xl:w-96 flex-col border-l border-border bg-card shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Detail
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
        <div className="px-4 py-4 space-y-4">
          {/* Title */}
          {n.title && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">Title</p>
              <p className="text-sm font-medium text-foreground">{n.title}</p>
            </div>
          )}

          <DetailRow
            icon={Clock}
            label="Received at"
            value={
              <span className="font-mono text-xs">
                {formatTimestamp(n.received_at)}
              </span>
            }
          />

          {n.sender_name && (
            <DetailRow
              icon={Tag}
              label="Sender"
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
              label="Tags"
              value={
                <div className="flex flex-wrap gap-1.5 mt-0.5">
                  {tags.map((tag) => {
                    const rule = rules.find((r) => r.name === tag);
                    const colors = rule ? TAG_COLOR_CLASSES[rule.color] : TAG_COLOR_CLASSES.slate;
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

          {n.source_ip && (
            <DetailRow
              icon={Wifi}
              label="Source IP"
              value={<span className="font-mono text-xs">{n.source_ip}</span>}
            />
          )}

          {Object.keys(n.custom_fields ?? {}).length > 0 && (
            <>
              <Separator />
              <DetailRow
                icon={Braces}
                label="Custom fields"
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
            label="Message"
            value={
              <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed bg-muted rounded-md p-3 text-foreground">
                {n.message}
              </pre>
            }
          />

          <div>
            <p className="text-[11px] text-muted-foreground mb-1">ID</p>
            <p className="font-mono text-[11px] text-muted-foreground break-all">{n.id}</p>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}
