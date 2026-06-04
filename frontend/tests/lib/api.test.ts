import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { notificationsKey } from "@/lib/api";

// ---------------------------------------------------------------------------
// notificationsKey — URL shape
// ---------------------------------------------------------------------------

describe("notificationsKey", () => {
  it("includes page and page_size", () => {
    const key = notificationsKey(1, "");
    expect(key).toContain("page=1");
    expect(key).toContain("page_size=20");
  });

  it("uses default page_size of 20", () => {
    expect(notificationsKey(2, "")).toContain("page_size=20");
  });

  it("accepts a custom page_size", () => {
    expect(notificationsKey(1, "", 50)).toContain("page_size=50");
  });

  it("does not include q param when query is empty string", () => {
    const key = notificationsKey(1, "");
    expect(key).not.toContain("&q=");
  });

  it("includes url-encoded q param when query is provided", () => {
    const key = notificationsKey(1, "docker error");
    expect(key).toContain("q=docker%20error");
  });

  it("produces keys that differ by page", () => {
    expect(notificationsKey(1, "")).not.toBe(notificationsKey(2, ""));
  });

  it("produces keys that differ by search term", () => {
    expect(notificationsKey(1, "foo")).not.toBe(notificationsKey(1, "bar"));
  });

  it("starts with /notifications path segment", () => {
    expect(notificationsKey(1, "")).toMatch(/^\/notifications/);
  });
});

// ---------------------------------------------------------------------------
// apiFetch error handling — mock global fetch
// ---------------------------------------------------------------------------

describe("apiFetch error handling", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    // Reset between tests
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("throws when response is not ok", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      text: () => Promise.resolve("Forbidden"),
    } as unknown as Response);

    const { fetchNotifications } = await import("@/lib/api");
    await expect(fetchNotifications("/notifications?page=1&page_size=20")).rejects.toThrow();
  });

  it("resolves when response is ok", async () => {
    const mockPayload = { items: [], total: 0, page: 1, page_size: 20, pages: 1 };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockPayload),
    } as unknown as Response);

    const { fetchNotifications } = await import("@/lib/api");
    const result = await fetchNotifications("/notifications?page=1&page_size=20");
    expect(result.total).toBe(0);
    expect(result.items).toEqual([]);
  });
});
