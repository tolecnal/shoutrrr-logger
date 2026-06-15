"use client";

/**
 * Server-backed per-user notification-log views.
 *
 *  - useLogTabs:      the user's open, named, ordered tabs. Persisted server
 *                     side so they survive logout / session expiry / device
 *                     changes. Which tab is focused is remembered locally.
 *  - useSavedSearches: the user's named, reusable search library.
 *
 * Both store the same LogFilterState blob (see lib/types). The helpers below
 * normalize and compare those blobs so callers can detect "in sync with the
 * server" without worrying about missing keys or field order.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";

import {
  createLogTab,
  createSavedSearch,
  deleteLogTab,
  deleteSavedSearch,
  fetchLogTabs,
  fetchSavedSearches,
  reorderLogTabs,
  updateLogTab,
  updateSavedSearch,
} from "@/lib/api";
import type { LogFilterState, LogTabOut, SavedSearchOut } from "@/lib/types";

export const DEFAULT_FILTER_STATE: LogFilterState = {
  query: "",
  scope: "all",
  time_range: "all",
  custom_after: "",
  custom_before: "",
  active_label: null,
  group_field: null,
  group_values: [],
};

/** Fill in any missing keys with defaults so partial/legacy blobs load cleanly. */
export function normalizeFilterState(f?: Partial<LogFilterState> | null): LogFilterState {
  return { ...DEFAULT_FILTER_STATE, ...(f ?? {}) };
}

/** Value equality over the normalized blob (key order is fixed by the spread). */
export function filterStatesEqual(a?: Partial<LogFilterState> | null, b?: Partial<LogFilterState> | null): boolean {
  return JSON.stringify(normalizeFilterState(a)) === JSON.stringify(normalizeFilterState(b));
}

const ACTIVE_TAB_KEY = "shoutrrr-logger:active-tab";

export function useLogTabs(defaultTabName: string) {
  const { data, mutate, isLoading } = useSWR("/me/tabs", fetchLogTabs, {
    revalidateOnFocus: false,
  });

  const tabs = useMemo<LogTabOut[]>(
    () => (data ? [...data].sort((a, b) => a.position - b.position) : []),
    [data],
  );

  const [activeTabId, setActiveTabIdState] = useState<string | null>(null);

  // Hydrate the focused tab from localStorage after mount (avoids SSR mismatch).
  useEffect(() => {
    try {
      setActiveTabIdState(localStorage.getItem(ACTIVE_TAB_KEY));
    } catch {
      // ignore
    }
  }, []);

  const setActiveTabId = useCallback((id: string | null) => {
    setActiveTabIdState(id);
    try {
      if (id) localStorage.setItem(ACTIVE_TAB_KEY, id);
      else localStorage.removeItem(ACTIVE_TAB_KEY);
    } catch {
      // ignore
    }
  }, []);

  // Ensure the user always has at least one tab, and that the focused id is
  // valid. Auto-creates a single default tab the first time a user with none
  // loads the log.
  const ensuringRef = useRef(false);
  useEffect(() => {
    if (isLoading || !data) return;
    if (data.length === 0) {
      if (ensuringRef.current) return;
      ensuringRef.current = true;
      createLogTab({ name: defaultTabName, filters: DEFAULT_FILTER_STATE })
        .then(async (created) => {
          await mutate();
          setActiveTabId(created.id);
        })
        .catch(() => {
          ensuringRef.current = false;
        });
      return;
    }
    if (!activeTabId || !data.some((t) => t.id === activeTabId)) {
      const first = [...data].sort((a, b) => a.position - b.position)[0];
      setActiveTabId(first.id);
    }
  }, [isLoading, data, activeTabId, defaultTabName, mutate, setActiveTabId]);

  const activeTab = useMemo(
    () => tabs.find((t) => t.id === activeTabId) ?? null,
    [tabs, activeTabId],
  );

  const create = useCallback(
    async (name: string, filters: LogFilterState) => {
      const created = await createLogTab({ name, filters });
      await mutate();
      setActiveTabId(created.id);
      return created;
    },
    [mutate, setActiveTabId],
  );

  const rename = useCallback(
    async (id: string, name: string) => {
      // Optimistic so the tab label updates instantly.
      await mutate(
        (prev) => prev?.map((t) => (t.id === id ? { ...t, name } : t)),
        { revalidate: false },
      );
      await updateLogTab(id, { name });
      await mutate();
    },
    [mutate],
  );

  /** Persist a tab's filter blob. Optimistic; no revalidation flicker. */
  const saveFilters = useCallback(
    async (id: string, filters: LogFilterState) => {
      await mutate(
        (prev) => prev?.map((t) => (t.id === id ? { ...t, filters } : t)),
        { revalidate: false },
      );
      try {
        await updateLogTab(id, { filters });
      } catch {
        await mutate(); // resync on failure
      }
    },
    [mutate],
  );

  const remove = useCallback(
    async (id: string) => {
      const remaining = tabs.filter((t) => t.id !== id);
      await deleteLogTab(id);
      await mutate();
      if (activeTabId === id) {
        setActiveTabId(remaining.length ? remaining[0].id : null);
      }
    },
    [tabs, activeTabId, mutate, setActiveTabId],
  );

  /** Apply a new left-to-right order (full ordered id list). Optimistic. */
  const reorder = useCallback(
    async (ids: string[]) => {
      const rank = new Map(ids.map((id, i) => [id, i]));
      await mutate(
        (prev) =>
          prev?.map((t) => (rank.has(t.id) ? { ...t, position: rank.get(t.id)! } : t)),
        { revalidate: false },
      );
      try {
        await reorderLogTabs(ids);
        await mutate();
      } catch {
        await mutate(); // resync on failure
      }
    },
    [mutate],
  );

  return {
    tabs,
    activeTab,
    activeTabId,
    setActiveTabId,
    isLoading,
    createTab: create,
    renameTab: rename,
    saveTabFilters: saveFilters,
    deleteTab: remove,
    reorderTabs: reorder,
  };
}

export function useSavedSearches() {
  const { data, mutate, isLoading } = useSWR("/me/saved-searches", fetchSavedSearches, {
    revalidateOnFocus: false,
  });

  const searches = useMemo<SavedSearchOut[]>(() => data ?? [], [data]);

  const create = useCallback(
    async (name: string, filters: LogFilterState) => {
      const created = await createSavedSearch({ name, filters });
      await mutate();
      return created;
    },
    [mutate],
  );

  const rename = useCallback(
    async (id: string, name: string) => {
      const updated = await updateSavedSearch(id, { name });
      await mutate();
      return updated;
    },
    [mutate],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteSavedSearch(id);
      await mutate();
    },
    [mutate],
  );

  return { searches, isLoading, createSearch: create, renameSearch: rename, deleteSearch: remove };
}
