"use client";

/**
 * useTagRules
 *
 * Stores user-defined tag classification rules in localStorage.
 * Each rule contains:
 *   - id:       unique identifier
 *   - name:     display label (e.g. "Update", "Error")
 *   - color:    tailwind bg color key used for the badge (e.g. "blue", "red")
 *   - patterns: array of regex strings tested against the notification message + title
 *   - enabled:  if false the rule is skipped
 *
 * classifyNotification(notification, rules) returns the names of all
 * matching tags for a given notification.
 */

import { useCallback, useEffect, useState } from "react";
import type { NotificationOut } from "./types";

export type TagColor =
  | "slate"
  | "blue"
  | "green"
  | "yellow"
  | "orange"
  | "red"
  | "purple"
  | "pink"
  | "teal";

export interface TagRule {
  id: string;
  name: string;
  color: TagColor;
  patterns: string[]; // regex strings — any match → tag applied
  enabled: boolean;
  /** When true, any notification that matches this rule is hidden entirely,
   *  regardless of what other tags it carries. */
  exclude: boolean;
}

// Sensible defaults so the feature is useful out of the box
const DEFAULT_RULES: TagRule[] = [
  {
    id: "default-startup",
    name: "Startup",
    color: "teal",
    patterns: [
      "(?i)watchtower \\d+\\.\\d+",
      "(?i)next scheduled run",
      "(?i)using notifications",
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

const STORAGE_KEY = "shoutrrr-logger:tag-rules";

// Tailwind color map — the badge component reads these
export const TAG_COLOR_CLASSES: Record<TagColor, { bg: string; text: string; border: string }> = {
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

function loadRules(): TagRule[] {
  if (typeof window === "undefined") return DEFAULT_RULES;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_RULES;
    const parsed = JSON.parse(raw) as TagRule[];
    if (!Array.isArray(parsed) || parsed.length === 0) return DEFAULT_RULES;
    // Backfill `exclude` for rules saved before the field existed
    return parsed.map((r) => ({ exclude: false, ...r }));
  } catch {
    return DEFAULT_RULES;
  }
}

function saveRules(rules: TagRule[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(rules));
  } catch {
    // ignore quota errors
  }
}

/** Returns the tag names (in rule order) that match the given notification. */
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

/** Returns the tag names (in rule order) that match the given notification. */
export function classifyNotification(
  notification: NotificationOut,
  rules: TagRule[]
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
  rules: TagRule[]
): boolean {
  const haystack = [notification.message, notification.title ?? ""].join(" ");

  return rules
    .filter((r) => r.enabled && r.exclude)
    .some((r) => matchesAnyPattern(haystack, r.patterns));
}

export function useTagRules() {
  const [rules, setRulesState] = useState<TagRule[]>(DEFAULT_RULES);

  useEffect(() => {
    setRulesState(loadRules());
  }, []);

  const setRules = useCallback((next: TagRule[]) => {
    saveRules(next);
    setRulesState(next);
  }, []);

  const addRule = useCallback(
    (rule: Omit<TagRule, "id">) => {
      const newRule: TagRule = {
        ...rule,
        id: crypto.randomUUID(),
      };
      setRules([...rules, newRule]);
    },
    [rules, setRules]
  );

  const updateRule = useCallback(
    (id: string, patch: Partial<Omit<TagRule, "id">>) => {
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
