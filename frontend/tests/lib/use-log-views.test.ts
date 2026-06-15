import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  DEFAULT_FILTER_STATE,
  normalizeFilterState,
  filterStatesEqual,
} from "@/lib/use-log-views";
import {
  createSavedSearch,
  updateSavedSearch,
  deleteSavedSearch,
  createLogTab,
  updateLogTab,
  deleteLogTab,
  reorderLogTabs,
} from "@/lib/api";
import type { LogFilterState } from "@/lib/types";

// ---------------------------------------------------------------------------
// Filter-state helpers (pure)
// ---------------------------------------------------------------------------

describe("normalizeFilterState", () => {
  it("returns the defaults for null/undefined", () => {
    expect(normalizeFilterState(null)).toEqual(DEFAULT_FILTER_STATE);
    expect(normalizeFilterState(undefined)).toEqual(DEFAULT_FILTER_STATE);
  });

  it("fills missing keys from defaults while keeping provided ones", () => {
    const out = normalizeFilterState({ query: "sender:icinga2", scope: "mine" });
    expect(out.query).toBe("sender:icinga2");
    expect(out.scope).toBe("mine");
    expect(out.time_range).toBe("all");
    expect(out.active_label).toBeNull();
    expect(out.group_values).toEqual([]);
  });

  it("does not mutate the shared defaults object", () => {
    const out = normalizeFilterState({ group_values: ["a"] });
    out.group_values.push("b");
    expect(DEFAULT_FILTER_STATE.group_values).toEqual([]);
  });
});

describe("filterStatesEqual", () => {
  const base: LogFilterState = {
    query: "x",
    scope: "global",
    time_range: "24h",
    custom_after: "",
    custom_before: "",
    active_label: "prod",
    group_field: "env",
    group_values: ["a", "b"],
  };

  it("treats value-equal blobs as equal regardless of key order", () => {
    const reordered = {
      group_values: ["a", "b"],
      group_field: "env",
      active_label: "prod",
      custom_before: "",
      custom_after: "",
      time_range: "24h",
      scope: "global" as const,
      query: "x",
    };
    expect(filterStatesEqual(base, reordered)).toBe(true);
  });

  it("treats a partial blob as equal to its normalized full form", () => {
    expect(filterStatesEqual({ query: "x" }, normalizeFilterState({ query: "x" }))).toBe(true);
  });

  it("detects differences in query", () => {
    expect(filterStatesEqual(base, { ...base, query: "y" })).toBe(false);
  });

  it("detects differences in group_values order", () => {
    expect(filterStatesEqual(base, { ...base, group_values: ["b", "a"] })).toBe(false);
  });

  it("considers the empty default equal to itself", () => {
    expect(filterStatesEqual(DEFAULT_FILTER_STATE, {})).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// API client — saved searches & log tabs (mock global fetch)
// ---------------------------------------------------------------------------

describe("saved-search & log-tab API", () => {
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

  const lastRequest = (): { url: string; init: RequestInit } => {
    const [url, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0] as [
      string,
      RequestInit,
    ];
    return { url, init };
  };

  it("creates a saved search with name + filters in the body", async () => {
    await createSavedSearch({ name: "Crit", filters: DEFAULT_FILTER_STATE });
    const { url, init } = lastRequest();
    expect(url).toBe("/api/v1/me/saved-searches");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      name: "Crit",
      filters: DEFAULT_FILTER_STATE,
    });
  });

  it("updates a saved search via PATCH on its id", async () => {
    await updateSavedSearch("s-1", { name: "Renamed" });
    const { url, init } = lastRequest();
    expect(url).toBe("/api/v1/me/saved-searches/s-1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ name: "Renamed" });
  });

  it("deletes a saved search", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 204 } as unknown as Response);
    await deleteSavedSearch("s-1");
    const { url, init } = lastRequest();
    expect(url).toBe("/api/v1/me/saved-searches/s-1");
    expect(init.method).toBe("DELETE");
  });

  it("creates a log tab", async () => {
    await createLogTab({ name: "Ops", filters: DEFAULT_FILTER_STATE });
    const { url, init } = lastRequest();
    expect(url).toBe("/api/v1/me/tabs");
    expect(init.method).toBe("POST");
  });

  it("updates a log tab's filters via PATCH", async () => {
    await updateLogTab("t-1", { filters: { ...DEFAULT_FILTER_STATE, query: "x" } });
    const { url, init } = lastRequest();
    expect(url).toBe("/api/v1/me/tabs/t-1");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string).filters.query).toBe("x");
  });

  it("deletes a log tab", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 204 } as unknown as Response);
    await deleteLogTab("t-1");
    const { url, init } = lastRequest();
    expect(url).toBe("/api/v1/me/tabs/t-1");
    expect(init.method).toBe("DELETE");
  });

  it("reorders tabs via PUT /me/tabs/order with an ids array", async () => {
    await reorderLogTabs(["t-2", "t-1"]);
    const { url, init } = lastRequest();
    expect(url).toBe("/api/v1/me/tabs/order");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body as string)).toEqual({ ids: ["t-2", "t-1"] });
  });
});
