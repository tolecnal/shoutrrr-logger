import { describe, it, expect } from "vitest";
import { FRONTEND_VERSION, API_VERSION_PREFIX } from "@/lib/version";

describe("version constants", () => {
  it("FRONTEND_VERSION is a non-empty string", () => {
    expect(typeof FRONTEND_VERSION).toBe("string");
    expect(FRONTEND_VERSION.length).toBeGreaterThan(0);
  });

  it("FRONTEND_VERSION follows semver format MAJOR.MINOR.PATCH", () => {
    const parts = FRONTEND_VERSION.split(".");
    expect(parts).toHaveLength(3);
    parts.forEach((part) => {
      expect(Number.isInteger(Number(part))).toBe(true);
    });
  });

  it("API_VERSION_PREFIX is a non-empty string", () => {
    expect(typeof API_VERSION_PREFIX).toBe("string");
    expect(API_VERSION_PREFIX.length).toBeGreaterThan(0);
  });

  it("API_VERSION_PREFIX starts with 'v'", () => {
    expect(API_VERSION_PREFIX).toMatch(/^v\d+/);
  });

  it("API_VERSION_PREFIX matches expected current value", () => {
    expect(API_VERSION_PREFIX).toBe("v1");
  });

  it("FRONTEND_VERSION is read from env, not the fallback", () => {
    // vitest.config.ts injects NEXT_PUBLIC_APP_VERSION from package.json;
    // if it were missing the fallback "0.0.0" would be returned instead.
    expect(FRONTEND_VERSION).not.toBe("0.0.0");
  });
});
