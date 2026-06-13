"use client";

import { AlertTriangle } from "lucide-react";

/**
 * Amber warning shown to users when the admin master switch
 * (`user_external_delivery_enabled`) is off, so they understand why their
 * plugins / alert emails aren't being delivered. Used in Preferences →
 * My Tokens, Alert Rules, and My Plugins for consistent messaging.
 */
export function ExternalDeliveryWarning({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-md border border-yellow-500/40 bg-yellow-500/10 px-3 py-2 text-xs text-yellow-700 dark:text-yellow-400"
    >
      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
      <span>{message}</span>
    </div>
  );
}
