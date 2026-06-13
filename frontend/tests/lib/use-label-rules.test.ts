import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  classifyNotification,
  isExcluded,
  useLabelRules,
  type LabelRule,
} from "@/lib/use-label-rules";
import type { NotificationOut } from "@/lib/types";

const STORAGE_KEY = "shoutrrr-logger:label-rules";
const LEGACY_STORAGE_KEY = "shoutrrr-logger:tag-rules";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeNotif(overrides: Partial<NotificationOut> = {}): NotificationOut {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    message: "container updated successfully",
    title: null,
    sender_name: "myhost",
    received_at: "2024-06-01T12:00:00Z",
    source_ip: "127.0.0.1",
    severity: "info",
    tags: [],
    fingerprint: null,
    occurrences: 1,
    state: "new",
    last_received_at: "2024-06-01T12:00:00Z",
    custom_fields: {},
    can_delete: true,
    ...overrides,
  };
}

function makeRule(overrides: Partial<LabelRule> = {}): LabelRule {
  return {
    id: "rule-1",
    name: "Test",
    color: "blue",
    patterns: ["(?i)updated"],
    enabled: true,
    exclude: false,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// classifyNotification
// ---------------------------------------------------------------------------

describe("classifyNotification", () => {
  it("returns matching rule names", () => {
    const notif = makeNotif({ message: "container updated to v2" });
    const rules = [makeRule({ name: "Update", patterns: ["(?i)updated"] })];
    expect(classifyNotification(notif, rules)).toEqual(["Update"]);
  });

  it("returns empty array when no rules match", () => {
    const notif = makeNotif({ message: "startup report" });
    const rules = [makeRule({ name: "Error", patterns: ["(?i)error"] })];
    expect(classifyNotification(notif, rules)).toEqual([]);
  });

  it("returns multiple matching labels in rule order", () => {
    const notif = makeNotif({ message: "error: update failed" });
    const rules = [
      makeRule({ id: "r1", name: "Error", patterns: ["(?i)error"] }),
      makeRule({ id: "r2", name: "Update", patterns: ["(?i)update"] }),
    ];
    expect(classifyNotification(notif, rules)).toEqual(["Error", "Update"]);
  });

  it("skips disabled rules", () => {
    const notif = makeNotif({ message: "container updated" });
    const rules = [makeRule({ name: "Update", patterns: ["(?i)updated"], enabled: false })];
    expect(classifyNotification(notif, rules)).toEqual([]);
  });

  it("matches against title as well as message", () => {
    const notif = makeNotif({ message: "some body text", title: "Deployment Error" });
    const rules = [makeRule({ name: "Error", patterns: ["(?i)error"] })];
    expect(classifyNotification(notif, rules)).toEqual(["Error"]);
  });

  it("handles case-insensitive (?i) prefix correctly", () => {
    const notif = makeNotif({ message: "UPDATED container" });
    const rules = [makeRule({ patterns: ["(?i)updated"] })];
    expect(classifyNotification(notif, rules)).not.toEqual([]);
  });

  it("handles patterns without (?i) as case-sensitive", () => {
    const notif = makeNotif({ message: "UPDATED container" });
    const rules = [makeRule({ patterns: ["updated"] })]; // no (?i)
    expect(classifyNotification(notif, rules)).toEqual([]);
  });

  it("skips rules with invalid regex patterns without throwing", () => {
    const notif = makeNotif({ message: "some message" });
    const rules = [makeRule({ patterns: ["[invalid("] })];
    expect(() => classifyNotification(notif, rules)).not.toThrow();
    expect(classifyNotification(notif, rules)).toEqual([]);
  });

  it("returns empty array when rules list is empty", () => {
    const notif = makeNotif();
    expect(classifyNotification(notif, [])).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// isExcluded
// ---------------------------------------------------------------------------

describe("isExcluded", () => {
  it("returns true when an exclude rule matches", () => {
    const notif = makeNotif({ message: "Watchtower 1.7 using Docker API" });
    const rules = [
      makeRule({
        name: "Startup",
        patterns: ["(?i)using docker api"],
        exclude: true,
      }),
    ];
    expect(isExcluded(notif, rules)).toBe(true);
  });

  it("returns false when exclude rule is disabled", () => {
    const notif = makeNotif({ message: "startup report" });
    const rules = [
      makeRule({
        patterns: ["(?i)startup"],
        exclude: true,
        enabled: false,
      }),
    ];
    expect(isExcluded(notif, rules)).toBe(false);
  });

  it("returns false when exclude flag is false even if pattern matches", () => {
    const notif = makeNotif({ message: "updated container" });
    const rules = [makeRule({ patterns: ["(?i)updated"], exclude: false })];
    expect(isExcluded(notif, rules)).toBe(false);
  });

  it("returns false when no patterns match", () => {
    const notif = makeNotif({ message: "update complete" });
    const rules = [makeRule({ patterns: ["(?i)error"], exclude: true })];
    expect(isExcluded(notif, rules)).toBe(false);
  });

  it("returns true if any one of multiple exclude rules matches", () => {
    const notif = makeNotif({ message: "startup sequence initiated" });
    const rules = [
      makeRule({ id: "r1", patterns: ["(?i)error"], exclude: true }),
      makeRule({ id: "r2", patterns: ["(?i)startup"], exclude: true }),
    ];
    expect(isExcluded(notif, rules)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// useLabelRules — legacy storage key migration
// ---------------------------------------------------------------------------

describe("useLabelRules legacy storage migration", () => {
  beforeEach(() => {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(LEGACY_STORAGE_KEY);
  });

  it("migrates rules saved under the old 'tag-rules' key on first load", async () => {
    const legacyRules = [makeRule({ id: "custom-1", name: "Custom" })];
    localStorage.setItem(LEGACY_STORAGE_KEY, JSON.stringify(legacyRules));

    const { result } = renderHook(() => useLabelRules());

    await waitFor(() => {
      expect(result.current.rules.map((r) => r.id)).toEqual(["custom-1"]);
    });

    expect(localStorage.getItem(LEGACY_STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem(STORAGE_KEY)).not.toBeNull();
  });

  it("leaves an existing 'label-rules' key untouched even if a legacy key is present", async () => {
    const currentRules = [makeRule({ id: "current-1", name: "Current" })];
    const legacyRules = [makeRule({ id: "legacy-1", name: "Legacy" })];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(currentRules));
    localStorage.setItem(LEGACY_STORAGE_KEY, JSON.stringify(legacyRules));

    const { result } = renderHook(() => useLabelRules());

    await waitFor(() => {
      expect(result.current.rules.map((r) => r.id)).toEqual(["current-1"]);
    });

    expect(localStorage.getItem(LEGACY_STORAGE_KEY)).not.toBeNull();
  });
});
