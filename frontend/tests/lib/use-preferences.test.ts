/**
 * Tests for the pure formatting functions extracted from usePreferences.
 *
 * formatTimestamp and formatTime are closure functions that depend on
 * prefs.timeFormat. We test them by calling the underlying formatting
 * logic directly via Intl.DateTimeFormat to avoid needing React hooks.
 */
import { describe, it, expect } from "vitest";

// ---------------------------------------------------------------------------
// Replicate the formatting logic from usePreferences so we can unit-test it
// without mounting a hook.
// ---------------------------------------------------------------------------

type TimeFormat = "locale" | "12h" | "24h";

function formatTimestamp(iso: string, timeFormat: TimeFormat): string {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return iso;

  const hourCycle: "h23" | "h12" | undefined =
    timeFormat === "24h" ? "h23" : timeFormat === "12h" ? "h12" : undefined;

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hourCycle,
  }).format(date);
}

function formatTime(iso: string, timeFormat: TimeFormat): string {
  const date = new Date(iso);
  if (isNaN(date.getTime())) return iso;

  const hourCycle: "h23" | "h12" | undefined =
    timeFormat === "24h" ? "h23" : timeFormat === "12h" ? "h12" : undefined;

  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hourCycle,
  }).format(date);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const FIXED_ISO = "2024-06-01T14:05:03Z";

describe("formatTimestamp", () => {
  it("returns a non-empty string for a valid ISO date", () => {
    const result = formatTimestamp(FIXED_ISO, "locale");
    expect(typeof result).toBe("string");
    expect(result.length).toBeGreaterThan(0);
  });

  it("returns the input unchanged for an invalid date string", () => {
    const bad = "not-a-date";
    expect(formatTimestamp(bad, "locale")).toBe(bad);
  });

  it("24h and 12h modes produce different strings", () => {
    const h24 = formatTimestamp(FIXED_ISO, "24h");
    const h12 = formatTimestamp(FIXED_ISO, "12h");
    // They format the same timestamp so they differ only in the hour representation
    expect(h24).not.toBe(h12);
  });

  it("result includes the year", () => {
    const result = formatTimestamp(FIXED_ISO, "locale");
    expect(result).toContain("2024");
  });

  it("24h result does not contain AM/PM indicators", () => {
    const result = formatTimestamp(FIXED_ISO, "24h");
    // h23 forces 24-hour format — no am/pm in en-US
    expect(result.toLowerCase()).not.toMatch(/am|pm/);
  });
});

describe("formatTime", () => {
  it("returns only time portion (no year)", () => {
    const result = formatTime(FIXED_ISO, "24h");
    expect(result).not.toContain("2024");
  });

  it("returns the input unchanged for an invalid date string", () => {
    const bad = "bad-date";
    expect(formatTime(bad, "locale")).toBe(bad);
  });

  it("24h and 12h modes produce different time strings", () => {
    const h24 = formatTime(FIXED_ISO, "24h");
    const h12 = formatTime(FIXED_ISO, "12h");
    expect(h24).not.toBe(h12);
  });

  it("result is shorter than full timestamp", () => {
    const full = formatTimestamp(FIXED_ISO, "locale");
    const short = formatTime(FIXED_ISO, "locale");
    expect(short.length).toBeLessThan(full.length);
  });
});
