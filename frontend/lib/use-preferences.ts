"use client";

/**
 * usePreferences
 *
 * Persists user preferences in localStorage. Currently manages:
 *   - timeFormat: "locale" | "12h" | "24h"
 *     "locale" (default) uses the browser's language to pick h23 vs h12 automatically.
 *
 * formatTimestamp(isoString) returns a locale-aware, human-readable datetime
 * string honouring the user's override.
 */

import { useCallback, useEffect, useState } from "react";

export type TimeFormat = "locale" | "12h" | "24h";

export interface Preferences {
  timeFormat: TimeFormat;
}

const STORAGE_KEY = "shoutrrr-logger:preferences";

const DEFAULTS: Preferences = {
  timeFormat: "locale",
};

function load(): Preferences {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch {
    return DEFAULTS;
  }
}

function save(prefs: Preferences) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // ignore quota errors
  }
}

export function usePreferences() {
  const [prefs, setPrefsState] = useState<Preferences>(DEFAULTS);

  // Hydrate from localStorage after mount (avoids SSR mismatch)
  useEffect(() => {
    setPrefsState(load());
  }, []);

  const setPrefs = useCallback((update: Partial<Preferences>) => {
    setPrefsState((prev) => {
      const next = { ...prev, ...update };
      save(next);
      return next;
    });
  }, []);

  /**
   * Format an ISO timestamp string according to the user's preference and
   * the browser's locale.
   *
   * Output examples (en-GB locale, date: 2026-06-03T14:05:03Z):
   *   locale → "3 Jun 2026, 14:05:03"
   *   24h    → "3 Jun 2026, 14:05:03"
   *   12h    → "3 Jun 2026, 2:05:03 pm"
   */
  const formatTimestamp = useCallback(
    (iso: string): string => {
      const date = new Date(iso);
      if (isNaN(date.getTime())) return iso;

      const hourCycle: "h23" | "h12" | undefined =
        prefs.timeFormat === "24h"
          ? "h23"
          : prefs.timeFormat === "12h"
          ? "h12"
          : undefined; // let locale decide

      return new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        hourCycle,
      }).format(date);
    },
    [prefs.timeFormat]
  );

  /**
   * Short variant — time only (for compact table cells).
   * Example: "14:05:03" or "2:05:03 pm"
   */
  const formatTime = useCallback(
    (iso: string): string => {
      const date = new Date(iso);
      if (isNaN(date.getTime())) return iso;

      const hourCycle: "h23" | "h12" | undefined =
        prefs.timeFormat === "24h"
          ? "h23"
          : prefs.timeFormat === "12h"
          ? "h12"
          : undefined;

      return new Intl.DateTimeFormat(undefined, {
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
        hourCycle,
      }).format(date);
    },
    [prefs.timeFormat]
  );

  return { prefs, setPrefs, formatTimestamp, formatTime };
}
