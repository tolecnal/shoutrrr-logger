"use client";

/**
 * The per-token external-delivery toggles (plugins, email alerts), shared by
 * the admin and personal token dialogs. Mirrors the backend
 * models.EXTERNAL_DELIVERY_CHANNELS — add a channel there and here together.
 */

import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

export interface TokenDeliveryValue {
  allow_plugin_dispatch: boolean;
  allow_email_alerts: boolean;
}

export function TokenDeliveryToggles({
  value,
  onChange,
  idPrefix,
  disabled = false,
}: {
  value: TokenDeliveryValue;
  onChange: (next: TokenDeliveryValue) => void;
  idPrefix: string;
  /** Locks both switches (e.g. an admin master switch is off). */
  disabled?: boolean;
}) {
  return (
    <div className="space-y-2">
      <Label className="text-xs">External delivery</Label>
      <div className="rounded-md border border-border/60 divide-y">
        <div className="flex items-center justify-between gap-4 p-3">
          <div className="space-y-0.5">
            <Label htmlFor={`${idPrefix}-allow-plugins`} className="text-xs font-medium">
              Allow plugins
            </Label>
            <p className="text-[11px] text-muted-foreground">
              Let plugins (Slack, Splunk, webhooks…) forward this token&apos;s notifications to
              third-party services.
            </p>
          </div>
          <Switch
            id={`${idPrefix}-allow-plugins`}
            checked={value.allow_plugin_dispatch}
            disabled={disabled}
            onCheckedChange={(v) => onChange({ ...value, allow_plugin_dispatch: v })}
          />
        </div>
        <div className="flex items-center justify-between gap-4 p-3">
          <div className="space-y-0.5">
            <Label htmlFor={`${idPrefix}-allow-email`} className="text-xs font-medium">
              Allow email alerts
            </Label>
            <p className="text-[11px] text-muted-foreground">
              Let matching alert rules email this token&apos;s notifications. In-app alerts are
              unaffected.
            </p>
          </div>
          <Switch
            id={`${idPrefix}-allow-email`}
            checked={value.allow_email_alerts}
            disabled={disabled}
            onCheckedChange={(v) => onChange({ ...value, allow_email_alerts: v })}
          />
        </div>
      </div>
    </div>
  );
}
