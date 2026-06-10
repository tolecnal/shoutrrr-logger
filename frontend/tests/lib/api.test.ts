import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { notificationsKey, auditLogsKey, updateToken, settingsToMap } from "@/lib/api";

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
// auditLogsKey — URL shape
// ---------------------------------------------------------------------------

describe("auditLogsKey", () => {
  it("includes page and page_size", () => {
    const key = auditLogsKey(1, 20);
    expect(key).toContain("page=1");
    expect(key).toContain("page_size=20");
  });

  it("uses default page_size of 20", () => {
    expect(auditLogsKey(2)).toContain("page_size=20");
  });

  it("does not include action param when not provided", () => {
    expect(auditLogsKey(1)).not.toContain("action=");
  });

  it("includes url-encoded action param when provided", () => {
    const key = auditLogsKey(1, 20, "settings.update");
    expect(key).toContain("action=settings.update");
  });

  it("produces keys that differ by page", () => {
    expect(auditLogsKey(1)).not.toBe(auditLogsKey(2));
  });

  it("produces keys that differ by action filter", () => {
    expect(auditLogsKey(1, 20, "user.create")).not.toBe(auditLogsKey(1, 20, "token.create"));
  });

  it("starts with /admin/audit-logs path segment", () => {
    expect(auditLogsKey(1)).toMatch(/^\/admin\/audit-logs/);
  });
});

// ---------------------------------------------------------------------------
// settingsToMap — defaults
// ---------------------------------------------------------------------------

describe("settingsToMap", () => {
  it("defaults rate_limit_per_minute to 0 when not present", () => {
    expect(settingsToMap([]).rate_limit_per_minute).toBe(0);
  });

  it("reads rate_limit_per_minute from the settings list", () => {
    const map = settingsToMap([
      {
        key: "rate_limit_per_minute",
        value: 42,
        label: "",
        description: "",
        default: 0,
        min_value: 0,
        max_value: 10000,
        unit: "",
      },
    ]);
    expect(map.rate_limit_per_minute).toBe(42);
  });
});

// ---------------------------------------------------------------------------
// updateToken — query param shape
// ---------------------------------------------------------------------------

describe("updateToken", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({}),
    } as unknown as Response);
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("sets rate_limit_override as a query param", async () => {
    await updateToken("tok-1", { rate_limit_override: 10 });
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("rate_limit_override=10");
    expect(url).not.toContain("clear_rate_limit_override");
  });

  it("sets clear_rate_limit_override as a query param", async () => {
    await updateToken("tok-1", { clear_rate_limit_override: true });
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("clear_rate_limit_override=true");
    expect(url).not.toMatch(/[^_]rate_limit_override=/);
  });

  it("omits rate-limit params when not provided", async () => {
    await updateToken("tok-1", { name: "renamed" });
    const url = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("name=renamed");
    expect(url).not.toContain("rate_limit_override");
    expect(url).not.toContain("clear_rate_limit_override");
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
