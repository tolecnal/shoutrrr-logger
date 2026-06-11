"use client";

/**
 * useLabelRules
 *
 * Stores user-defined label classification rules in localStorage.
 * Each rule contains:
 *   - id:       unique identifier
 *   - name:     display label (e.g. "Update", "Error")
 *   - color:    tailwind bg color key used for the badge (e.g. "blue", "red")
 *   - patterns: array of regex strings tested against the notification message + title
 *   - enabled:  if false the rule is skipped
 *
 * classifyNotification(notification, rules) returns the names of all
 * matching labels for a given notification.
 */

import { useCallback, useEffect, useState } from "react";
import type { NotificationOut } from "./types";

export type LabelColor =
  | "slate"
  | "blue"
  | "green"
  | "yellow"
  | "orange"
  | "red"
  | "purple"
  | "pink"
  | "teal";

export interface LabelRule {
  id: string;
  name: string;
  color: LabelColor;
  patterns: string[]; // regex strings — any match → label applied
  enabled: boolean;
  /** When true, any notification that matches this rule is hidden entirely,
   *  regardless of what other labels it carries. */
  exclude: boolean;
}

// Sensible defaults so the feature is useful out of the box
const DEFAULT_LABEL_RULES: LabelRule[] = [
  {
    id: "default-startup",
    name: "Startup",
    color: "teal",
    // These patterns match the Watchtower startup-only message lines.
    // Deliberately anchored/specific so they don't fire on update reports
    // that may also contain scheduling info in the same message blob.
    patterns: [
      // "Watchtower 1.17.2 using Docker API v1.54 [hostname]"
      "(?i)watchtower \\d+\\.\\d+.*using docker api",
      // "Using notifications: generic+http" — startup-only line
      "(?i)^using notifications:",
      // "Next scheduled run: 2026-06-04 04:00:00 UTC in N hours"
      "(?i)^next scheduled run:",
    ],
    enabled: true,
    exclude: false,
  },
  {
    id: "default-update",
    name: "Update",
    color: "blue",
    patterns: ["(?i)updat", "(?i)upgrade", "(?i)new version"],
    enabled: true,
    exclude: false,
  },
  {
    id: "default-error",
    name: "Error",
    color: "red",
    patterns: ["(?i)error", "(?i)fail", "(?i)exception", "(?i)critical"],
    enabled: true,
    exclude: false,
  },
  {
    id: "default-warning",
    name: "Warning",
    color: "yellow",
    patterns: ["(?i)warn", "(?i)caution", "(?i)deprecated"],
    enabled: true,
    exclude: false,
  },
  {
    id: "default-success",
    name: "Success",
    color: "green",
    patterns: ["(?i)success", "(?i)complete", "(?i)done", "(?i)ok"],
    enabled: true,
    exclude: false,
  },
];

const STORAGE_KEY = "shoutrrr-logger:label-rules";
const LEGACY_STORAGE_KEY = "shoutrrr-logger:tag-rules";

// Index default rules by ID for fast pattern lookups during migration
const DEFAULT_LABEL_RULES_BY_ID = new Map(DEFAULT_LABEL_RULES.map((r) => [r.id, r]));

// Tailwind color map — the badge component reads these
export const LABEL_COLOR_CLASSES: Record<LabelColor, { bg: string; text: string; border: string }> = {
  slate:  { bg: "bg-slate-100 dark:bg-slate-800",   text: "text-slate-700 dark:text-slate-300",   border: "border-slate-300 dark:border-slate-600" },
  blue:   { bg: "bg-blue-100 dark:bg-blue-900/40",  text: "text-blue-700 dark:text-blue-300",     border: "border-blue-300 dark:border-blue-700"   },
  green:  { bg: "bg-green-100 dark:bg-green-900/40",text: "text-green-700 dark:text-green-300",   border: "border-green-300 dark:border-green-700" },
  yellow: { bg: "bg-yellow-100 dark:bg-yellow-900/40",text:"text-yellow-700 dark:text-yellow-300",border: "border-yellow-300 dark:border-yellow-700"},
  orange: { bg: "bg-orange-100 dark:bg-orange-900/40",text:"text-orange-700 dark:text-orange-300",border: "border-orange-300 dark:border-orange-700"},
  red:    { bg: "bg-red-100 dark:bg-red-900/40",    text: "text-red-700 dark:text-red-300",       border: "border-red-300 dark:border-red-700"     },
  purple: { bg: "bg-purple-100 dark:bg-purple-900/40",text:"text-purple-700 dark:text-purple-300",border: "border-purple-300 dark:border-purple-700"},
  pink:   { bg: "bg-pink-100 dark:bg-pink-900/40",  text: "text-pink-700 dark:text-pink-300",     border: "border-pink-300 dark:border-pink-700"   },
  teal:   { bg: "bg-teal-100 dark:bg-teal-900/40",  text: "text-teal-700 dark:text-teal-300",     border: "border-teal-300 dark:border-teal-700"   },
};

/**
 * Renamed from "shoutrrr-logger:tag-rules" to "shoutrrr-logger:label-rules"
 * to match the "Tag Rules" → "Labels" rename. Migrate any existing rules
 * stored under the old key so users don't lose their customizations.
 */
function migrateLegacyStorageKey() {
  if (typeof window === "undefined") return;
  if (localStorage.getItem(STORAGE_KEY) !== null) return;
  const legacy = localStorage.getItem(LEGACY_STORAGE_KEY);
  if (legacy === null) return;
  localStorage.setItem(STORAGE_KEY, legacy);
  localStorage.removeItem(LEGACY_STORAGE_KEY);
}

function loadRules(): LabelRule[] {
  if (typeof window === "undefined") return DEFAULT_LABEL_RULES;
  try {
    migrateLegacyStorageKey();
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_LABEL_RULES;
    // Rules saved before `exclude` existed won't have that field at runtime,
    // even though the persisted shape is asserted as LabelRule[] here.
    const parsed = JSON.parse(raw) as (Omit<LabelRule, "exclude"> & { exclude?: boolean })[];
    if (!Array.isArray(parsed) || parsed.length === 0) return DEFAULT_LABEL_RULES;
    return parsed.map((r) => {
      const def = DEFAULT_LABEL_RULES_BY_ID.get(r.id);
      return {
        // Backfill `exclude` for rules saved before the field existed
        exclude: false,
        ...r,
        // Always use the canonical patterns from DEFAULT_LABEL_RULES for
        // built-in rules so that pattern fixes are applied to existing
        // users automatically. User preferences (enabled, exclude, color,
        // name) are preserved via the spread above.
        ...(def ? { patterns: def.patterns } : {}),
      };
    });
  } catch {
    return DEFAULT_LABEL_RULES;
  }
}

function saveRules(rules: LabelRule[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(rules));
  } catch {
    // ignore quota errors
  }
}

/** Returns true if any pattern matches the given haystack. */
function matchesAnyPattern(haystack: string, patterns: string[]): boolean {
  return patterns.some((pattern) => {
    try {
      const cleaned = pattern.replace(/^\(\?i\)/, "");
      const flags = pattern.startsWith("(?i)") ? "i" : "";
      return new RegExp(cleaned, flags).test(haystack);
    } catch {
      return false;
    }
  });
}

/** Returns the label names (in rule order) that match the given notification. */
export function classifyNotification(
  notification: NotificationOut,
  rules: LabelRule[]
): string[] {
  const haystack = [notification.message, notification.title ?? ""].join(" ");

  return rules
    .filter((r) => r.enabled)
    .filter((r) => matchesAnyPattern(haystack, r.patterns))
    .map((r) => r.name);
}

/**
 * Returns true if the notification matches any rule that has `exclude: true`.
 * Excluded notifications should be hidden from the list entirely.
 */
export function isExcluded(
  notification: NotificationOut,
  rules: LabelRule[]
): boolean {
  const haystack = [notification.message, notification.title ?? ""].join(" ");

  return rules
    .filter((r) => r.enabled && r.exclude)
    .some((r) => matchesAnyPattern(haystack, r.patterns));
}

export function useLabelRules() {
  const [rules, setRulesState] = useState<LabelRule[]>(DEFAULT_LABEL_RULES);

  useEffect(() => {
    setRulesState(loadRules());
  }, []);

  const setRules = useCallback((next: LabelRule[]) => {
    saveRules(next);
    setRulesState(next);
  }, []);

  const addRule = useCallback(
    (rule: Omit<LabelRule, "id">) => {
      const newRule: LabelRule = {
        ...rule,
        id: crypto.randomUUID(),
      };
      setRules([...rules, newRule]);
    },
    [rules, setRules]
  );

  const updateRule = useCallback(
    (id: string, patch: Partial<Omit<LabelRule, "id">>) => {
      setRules(rules.map((r) => (r.id === id ? { ...r, ...patch } : r)));
    },
    [rules, setRules]
  );

  const deleteRule = useCallback(
    (id: string) => {
      setRules(rules.filter((r) => r.id !== id));
    },
    [rules, setRules]
  );

  const classify = useCallback(
    (notification: NotificationOut) => classifyNotification(notification, rules),
    [rules]
  );

  return { rules, setRules, addRule, updateRule, deleteRule, classify };
}
