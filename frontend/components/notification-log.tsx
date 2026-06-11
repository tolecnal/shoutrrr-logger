"use client";

import { useState, useCallback, useMemo, useEffect, useRef } from "react";
import useSWR from "swr";
import { Search, ChevronLeft, ChevronRight, ChevronDown, Download, RefreshCw, Inbox, X, ListFilter, Clock, FileJson, FileSpreadsheet, HelpCircle } from "lucide-react";
import { fetchNotifications, fetchSettings, fetchSearchFilters, notificationsKey, exportNotificationsUrl, settingsToMap } from "@/lib/api";
import type { NotificationOut } from "@/lib/types";
import { usePreferences } from "@/lib/use-preferences";
import { useTagRules, isExcluded, TAG_COLOR_CLASSES } from "@/lib/use-tag-rules";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { NotificationDetail } from "@/components/notification-detail";
import { SearchAutocomplete } from "./search-autocomplete";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Time range helpers
// ---------------------------------------------------------------------------

const PRESETS = [
  { value: "all", label: "All time" },
  { value: "15m", label: "Last 15 minutes" },
  { value: "1h", label: "Last hour" },
  { value: "3h", label: "Last 3 hours" },
  { value: "12h", label: "Last 12 hours" },
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last week" },
  { value: "custom", label: "Custom range…" },
] as const;

type Preset = (typeof PRESETS)[number]["value"];

function resolveTimeRange(
  preset: Preset,
  customAfter: string,
  customBefore: string
): { after?: string; before?: string } {
  const now = new Date();
  const ms = (n: number) => new Date(now.getTime() - n).toISOString();
  const M = 60_000;
  const H = 3_600_000;
  switch (preset) {
    case "15m": return { after: ms(15 * M) };
    case "1h":  return { after: ms(H) };
    case "3h":  return { after: ms(3 * H) };
    case "12h": return { after: ms(12 * H) };
    case "24h": return { after: ms(24 * H) };
    case "7d":  return { after: ms(7 * 24 * H) };
    case "custom": return {
      after:  customAfter  ? new Date(customAfter).toISOString()  : undefined,
      before: customBefore ? new Date(customBefore).toISOString() : undefined,
    };
    default: return {};
  }
}

const DEFAULT_PAGE_SIZE = 20;
// When filters are active we need a larger server page so that after
// client-side filtering we still have enough rows to fill the view.
const FILTERED_FETCH_SIZE = 100;

/** Stringifies a custom field value for comparison/display in the group-by UI. */
function customFieldValue(n: NotificationOut, key: string): string | null {
  const v = n.custom_fields?.[key];
  if (v === undefined || v === null) return null;
  return typeof v === "object" ? JSON.stringify(v) : String(v);
}

export function NotificationLog() {
  // Keyset pagination: cursorStack[pageIndex] is the cursor for the current
  // server page (cursorStack[0] is always null = first page). Moving forward
  // appends the response's next_cursor; moving back just steps through what
  // we've already visited.
  const [cursorStack, setCursorStack] = useState<(string | null)[]>([null]);
  const [pageIndex, setPageIndex] = useState(0);
  const [clientPage, setClientPage] = useState(1);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<NotificationOut | null>(null);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [groupField, setGroupField] = useState<string | null>(null);
  const [groupValues, setGroupValues] = useState<Set<string>>(new Set());
  // Scope filter: all = global + own private, global = global only, mine = own private only
  const [scope, setScope] = useState<"all" | "global" | "mine">("all");
  // Time range filter
  const [timeRange, setTimeRange] = useState<Preset>("all");
  const [customAfter, setCustomAfter] = useState("");
  const [customBefore, setCustomBefore] = useState("");
  // Bumped by the Refresh button so that preset "after" times recompute to now
  const [refreshNonce, setRefreshNonce] = useState(0);

  const searchInputRef = useRef<HTMLInputElement>(null);

  // Load app settings (page size, auto-refresh interval)
  const { data: settingsList } = useSWR("/settings", fetchSettings, { revalidateOnFocus: false });
  const { data: searchFilters } = useSWR("/notifications/search-filters", fetchSearchFilters, { 
    revalidateOnFocus: false, 
    dedupingInterval: 300000 
  });
  const appSettings = useMemo(
    () => (settingsList ? settingsToMap(settingsList) : null),
    [settingsList]
  );
  const pageSize = appSettings?.page_size ?? DEFAULT_PAGE_SIZE;
  const autoRefreshMs = ((appSettings?.auto_refresh_interval ?? 30)) * 1000;

  const { formatTimestamp, formatTime } = usePreferences();
  const { rules, classify } = useTagRules();

  // Are any client-side filters active?
  const hasExclude = useMemo(() => rules.some((r) => r.enabled && r.exclude), [rules]);
  const groupingActive = groupField !== null && groupValues.size > 0;
  const filtersActive = hasExclude || activeTag !== null || groupingActive;

  // When filters are active we fetch a large page so client-side filtering
  // has enough raw material. When filters are off, use normal server pagination.
  const fetchSize = filtersActive ? FILTERED_FETCH_SIZE : pageSize;
  const cursor = cursorStack[pageIndex];

  // Resolve the currently selected time range to ISO strings. Depends on
  // refreshNonce so clicking Refresh slides the preset window to "now".
  const { after: timeAfter, before: timeBefore } = useMemo(
    () => resolveTimeRange(timeRange, customAfter, customBefore),
    // refreshNonce intentionally included so preset windows recompute on Refresh
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [timeRange, customAfter, customBefore, refreshNonce]
  );

  const swrKey = useMemo(
    () => notificationsKey(cursor, query, fetchSize, timeAfter, timeBefore, scope),
    [cursor, query, fetchSize, timeAfter, timeBefore, scope]
  );

  const { data, isLoading, mutate } = useSWR(swrKey, fetchNotifications, {
    refreshInterval: autoRefreshMs > 0 ? autoRefreshMs : 0,
  });

  // Listen for real-time updates via Server-Sent Events (SSE)
  useEffect(() => {
    const url = new URL("/api/v1/notifications/stream", window.location.origin);
    const source = new EventSource(url.toString(), { withCredentials: true });

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload && (payload.event === "new" || payload.event === "update")) {
          // Re-fetch the current page to get the new or updated notifications
          mutate();
        }
      } catch (err) {
        // Ignore parse errors from ping messages or malformed data
      }
    };

    source.onerror = () => {
      // EventSource will automatically attempt to reconnect
    };

    return () => {
      source.close();
    };
  }, [mutate]);


  // Classify + exclude on every page fetch
  const classifiedItems = useMemo(() => {
    if (!data?.items) return [];
    return data.items
      .filter((n) => !isExcluded(n, rules))
      .map((n) => ({ notification: n, tags: classify(n) }));
  }, [data, rules, classify]);

  // Apply tag filter on top
  const filteredItems = useMemo(() => {
    if (!activeTag) return classifiedItems;
    return classifiedItems.filter(({ tags }) => tags.includes(activeTag));
  }, [classifiedItems, activeTag]);

  // Custom field keys present across the currently (tag-)filtered items —
  // populates the "Group by" field selector.
  const availableGroupFields = useMemo(() => {
    const keys = new Set<string>();
    for (const { notification: n } of filteredItems) {
      for (const k of Object.keys(n.custom_fields ?? {})) keys.add(k);
    }
    return Array.from(keys).sort();
  }, [filteredItems]);

  // Distinct values of the selected group field across the currently
  // (tag-)filtered items — populates the value chips. Computed independently
  // of the selected values themselves so toggling one doesn't shrink the list.
  const availableGroupValues = useMemo(() => {
    if (!groupField) return [];
    const values = new Set<string>();
    for (const { notification: n } of filteredItems) {
      const v = customFieldValue(n, groupField);
      if (v !== null) values.add(v);
    }
    return Array.from(values).sort();
  }, [filteredItems, groupField]);

  // Narrow down to notifications whose selected group field matches one of
  // the chosen values — this is the actual "group by" filter.
  const groupFilteredItems = useMemo(() => {
    if (!groupingActive || !groupField) return filteredItems;
    return filteredItems.filter(({ notification: n }) => {
      const v = customFieldValue(n, groupField);
      return v !== null && groupValues.has(v);
    });
  }, [filteredItems, groupingActive, groupField, groupValues]);

  // Client-side pagination over groupFilteredItems when filters are active
  const clientPageCount = Math.max(1, Math.ceil(groupFilteredItems.length / pageSize));

  // If the current client page exceeds available pages (e.g. filter was just
  // enabled and fewer items are visible), reset to page 1.
  useEffect(() => {
    if (clientPage > clientPageCount) setClientPage(1);
  }, [clientPage, clientPageCount]);

  // When filters are active we slice groupFilteredItems for display;
  // otherwise the server already returned exactly one page worth.
  const visibleItems = filtersActive
    ? groupFilteredItems.slice((clientPage - 1) * pageSize, clientPage * pageSize)
    : groupFilteredItems;

  // Pagination metadata shown in the UI
  // When filters are active: client-side page over filtered results + a
  // "load more from server" button when we've exhausted the current fetch.
  const displayPage = filtersActive ? clientPage : pageIndex + 1;
  const displayPages = filtersActive
    ? clientPageCount
    : data?.pages ?? 1;
  const displayTotal = filtersActive ? groupFilteredItems.length : data?.total ?? 0;
  // True when filters are active, we've consumed all locally-fetched items,
  // and the server has more rows beyond the current fetch.
  const serverHasMore =
    filtersActive &&
    clientPage >= clientPageCount &&
    data != null &&
    !!data.next_cursor;

  // Reset to the first page (drops any visited cursors).
  const resetPagination = useCallback(() => {
    setCursorStack([null]);
    setPageIndex(0);
    setClientPage(1);
  }, []);

  // Advance to the next server page, appending the current response's
  // next_cursor to the stack if we haven't visited it yet.
  const advanceServerPage = useCallback(() => {
    const next = data?.next_cursor;
    if (!next) return;
    setCursorStack((prev) => (pageIndex === prev.length - 1 ? [...prev, next] : prev));
    setPageIndex((p) => p + 1);
  }, [data, pageIndex]);

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      resetPagination();
      setQuery(search.trim());
    },
    [search, resetPagination]
  );

  const handleScopeChange = useCallback((s: "all" | "global" | "mine") => {
    setScope(s);
    resetPagination();
  }, [resetPagination]);

  const handleTimeRangeChange = useCallback((preset: Preset) => {
    setTimeRange(preset);
    resetPagination();
  }, [resetPagination]);

  const handleClearSearch = useCallback(() => {
    setSearch("");
    setQuery("");
    resetPagination();
  }, [resetPagination]);

  const handlePrev = useCallback(() => {
    if (filtersActive) {
      if (clientPage > 1) {
        setClientPage((p) => p - 1);
      } else if (pageIndex > 0) {
        setPageIndex((p) => p - 1);
        setClientPage(1);
      }
    } else {
      setPageIndex((p) => Math.max(0, p - 1));
    }
  }, [filtersActive, clientPage, pageIndex]);

  const handleNext = useCallback(() => {
    if (filtersActive) {
      if (clientPage < clientPageCount) {
        setClientPage((p) => p + 1);
      } else if (serverHasMore) {
        // Fetch the next server page; reset client page to 1 within new fetch
        advanceServerPage();
        setClientPage(1);
      }
    } else {
      advanceServerPage();
    }
  }, [filtersActive, clientPage, clientPageCount, serverHasMore, advanceServerPage]);

  const canGoPrev = filtersActive
    ? clientPage > 1 || pageIndex > 0
    : pageIndex > 0;
  const canGoNext = filtersActive
    ? clientPage < clientPageCount || serverHasMore
    : !!data?.next_cursor;

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const inInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.isContentEditable;

      // "/" — focus search (unless already in an input)
      if (e.key === "/" && !inInput && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
        return;
      }

      // Escape — clear search / close detail panel / clear filters
      if (e.key === "Escape") {
        if (document.activeElement === searchInputRef.current) {
          searchInputRef.current?.blur();
          return;
        }
        if (selected) { setSelected(null); return; }
        if (query) { handleClearSearch(); return; }
        if (activeTag) { setActiveTag(null); setClientPage(1); return; }
        if (timeRange !== "all") { handleTimeRangeChange("all"); return; }
        return;
      }

      // Arrow keys — pagination (only when no input is focused)
      if (inInput) return;
      if (e.key === "ArrowLeft" && canGoPrev) { e.preventDefault(); handlePrev(); }
      if (e.key === "ArrowRight" && canGoNext) { e.preventDefault(); handleNext(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [
    selected, query, activeTag, timeRange,
    canGoPrev, canGoNext, handlePrev, handleNext,
    handleClearSearch, handleTimeRangeChange,
  ]);

  const enabledTags = useMemo(
    () => rules.filter((r) => r.enabled).map((r) => r.name),
    [rules]
  );

  // Section the visible page by the selected group field's value, in the
  // order values were selected. Only built when grouping is active.
  const groupedSections = useMemo(() => {
    if (!groupingActive || !groupField) return null;
    const sections = new Map<string, typeof visibleItems>();
    for (const item of visibleItems) {
      // groupFilteredItems already guarantees a non-null matching value here.
      const v = customFieldValue(item.notification, groupField)!;
      const bucket = sections.get(v);
      if (bucket) bucket.push(item);
      else sections.set(v, [item]);
    }
    return Array.from(groupValues)
      .filter((v) => sections.has(v))
      .map((v) => ({ value: v, items: sections.get(v)! }));
  }, [groupingActive, groupField, groupValues, visibleItems]);

  return (
    <div className="flex flex-1 h-full">
      {/* List panel */}
      <div className="flex flex-col flex-1 min-w-0 border-r border-border">
        {/* Toolbar */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-card/50">
          <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1">
            <SearchAutocomplete 
              value={search} 
              onChange={setSearch} 
              filters={searchFilters} 
              inputRef={searchInputRef}
            />
            <Button type="submit" size="sm" variant="secondary" className="h-8">
              Search
            </Button>
            <Popover>
              <PopoverTrigger asChild>
                <Button type="button" size="sm" variant="ghost" className="h-8 w-8 p-0 text-muted-foreground" title="Search syntax help">
                  <HelpCircle className="h-4 w-4" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-80 p-4 text-sm bg-card border-border shadow-md" align="start">
                <div className="space-y-2">
                  <h4 className="font-medium leading-none">Advanced Search</h4>
                  <p className="text-muted-foreground">Search specific fields and use regular expressions.</p>
                  <ul className="space-y-1 mt-2 list-disc list-inside text-muted-foreground">
                    <li><code className="text-foreground">title:"error"</code> - exact substring in title</li>
                    <li><code className="text-foreground">message:/regex/</code> - regex search in message</li>
                    <li><code className="text-foreground">tag:env:prod</code> - search in tags</li>
                    <li><code className="text-foreground">sender:app*</code> - wildcard matching</li>
                    <li><code className="text-foreground">severity:info</code> - search by severity</li>
                    <li><code className="text-foreground">after:1h before:1d</code> - relative time filters</li>
                  </ul>
                  <p className="text-muted-foreground mt-2">Combine terms: <code className="text-foreground">severity:error tag:prod /timeout/</code></p>
                </div>
              </PopoverContent>
            </Popover>
            {query && (
              <Button
                type="button"
                size="sm"
                variant="ghost"
                className="h-8 text-muted-foreground"
                onClick={handleClearSearch}
              >
                Clear
              </Button>
            )}
          </form>
          <Button
            size="sm"
            variant="ghost"
            className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
            onClick={() => { setRefreshNonce((n) => n + 1); mutate(); }}
            title="Refresh"
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                size="sm"
                variant="ghost"
                className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                title="Export current view"
              >
                <Download className="h-3.5 w-3.5" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-40">
              <DropdownMenuItem asChild>
                <a
                  href={exportNotificationsUrl({ q: query || undefined, after: timeAfter, before: timeBefore, format: "csv" })}
                  download="notifications.csv"
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                  Export as CSV
                </a>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <a
                  href={exportNotificationsUrl({ q: query || undefined, after: timeAfter, before: timeBefore, format: "json" })}
                  download="notifications.json"
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <FileJson className="h-3.5 w-3.5" />
                  Export as JSON
                </a>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          {data && (
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {filtersActive
                ? `${displayTotal.toLocaleString()} visible`
                : `${data.total.toLocaleString()} total`}
            </span>
          )}
          {(displayPages > 1 || serverHasMore) && (
            <div className="flex items-center gap-1 text-xs text-muted-foreground whitespace-nowrap">
              <span>
                Page {displayPage} of {displayPages}
                {serverHasMore && "+"}
              </span>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                disabled={!canGoPrev}
                onClick={handlePrev}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                disabled={!canGoNext}
                onClick={handleNext}
                aria-label="Next page"
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>

        {/* Filter bar: always visible — scope + tag chips on the left, time range + group-by on the right */}
        <div className="flex items-center gap-1.5 px-4 py-2 border-b border-border bg-card/30 overflow-x-auto">
          {/* Scope filter */}
          <span className="text-[11px] text-muted-foreground shrink-0">Scope:</span>
          {(["all", "global", "mine"] as const).map((s) => (
            <button
              key={s}
              onClick={() => handleScopeChange(s)}
              className={cn(
                "px-2.5 py-0.5 rounded-full text-xs border transition-colors shrink-0",
                scope === s
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-transparent text-muted-foreground border-border hover:border-foreground/30 hover:text-foreground"
              )}
            >
              {s === "all" ? "All" : s === "global" ? "Global" : "My tokens"}
            </button>
          ))}

          {enabledTags.length > 0 && (
            <>
              <span className="text-[11px] text-muted-foreground shrink-0 ml-1 mr-1">Filter:</span>
              <button
                onClick={() => setActiveTag(null)}
                className={cn(
                  "px-2.5 py-0.5 rounded-full text-xs border transition-colors shrink-0",
                  activeTag === null
                    ? "bg-primary text-primary-foreground border-primary"
                    : "bg-transparent text-muted-foreground border-border hover:border-foreground/30 hover:text-foreground"
                )}
              >
                All
              </button>
              {rules
                .filter((r) => r.enabled)
                .map((rule) => {
                  const colors = TAG_COLOR_CLASSES[rule.color];
                  const isActive = activeTag === rule.name;
                  return (
                    <button
                      key={rule.id}
                      onClick={() => {
                        if (rule.exclude) return;
                        setActiveTag(isActive ? null : rule.name);
                        setClientPage(1);
                      }}
                      title={
                        rule.exclude
                          ? `"${rule.name}" is an exclude rule — matching messages are hidden`
                          : undefined
                      }
                      className={cn(
                        "px-2.5 py-0.5 rounded-full text-xs border transition-colors shrink-0",
                        rule.exclude
                          ? `${colors.bg} ${colors.text} ${colors.border} opacity-60 cursor-default line-through`
                          : isActive
                          ? `${colors.bg} ${colors.text} ${colors.border}`
                          : "bg-transparent text-muted-foreground border-border hover:border-foreground/30 hover:text-foreground"
                      )}
                    >
                      {rule.name}
                    </button>
                  );
                })}
              {activeTag && (
                <button
                  onClick={() => { setActiveTag(null); setClientPage(1); }}
                  className="h-7 w-5 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors shrink-0"
                  title="Clear tag filter"
                  aria-label="Clear tag filter"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </>
          )}

          {/* Pushes time range + group-by controls to the right */}
          <span className="flex-1" />

          <TimeRangeControl
            value={timeRange}
            customAfter={customAfter}
            customBefore={customBefore}
            onChange={handleTimeRangeChange}
            onCustomChange={(after, before) => {
              setCustomAfter(after);
              setCustomBefore(before);
              resetPagination();
            }}
          />

          {availableGroupFields.length > 0 && (
            <GroupByControl
              groupField={groupField}
              groupValues={groupValues}
              availableGroupFields={availableGroupFields}
              availableGroupValues={availableGroupValues}
              onFieldChange={(next) => {
                setGroupField(next);
                setGroupValues(new Set());
                resetPagination();
              }}
              onToggleValue={(value) => {
                setGroupValues((prev) => {
                  const next = new Set(prev);
                  if (next.has(value)) next.delete(value);
                  else next.add(value);
                  return next;
                });
                setClientPage(1);
              }}
              onSelectValues={(values) => {
                setGroupValues((prev) => new Set([...prev, ...values]));
                setClientPage(1);
              }}
              onClearValues={() => {
                setGroupValues(new Set());
                setClientPage(1);
              }}
            />
          )}
        </div>

        {/* Table */}
        <div className="flex-1 overflow-auto">
          {isLoading ? (
            <div className="space-y-px">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3 border-b border-border">
                  <Skeleton className="h-3 w-24 shrink-0" />
                  <Skeleton className="h-3 flex-1" />
                  <Skeleton className="h-3 w-16 shrink-0" />
                </div>
              ))}
            </div>
          ) : !visibleItems.length ? (
            <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
              <Inbox className="h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">
                {activeTag
                  ? `No notifications tagged "${activeTag}".`
                  : groupingActive
                  ? `No notifications match the selected ${groupField} value(s).`
                  : hasExclude
                  ? "No notifications match the current filters."
                  : query
                  ? "No notifications match your search."
                  : "No notifications yet."}
              </p>
              {serverHasMore && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => { advanceServerPage(); setClientPage(1); }}
                >
                  Load more from server
                </Button>
              )}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10 bg-card/90 backdrop-blur-sm border-b border-border">
                <tr>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-44">
                    Received
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-24">
                    Severity
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-32">
                    Sender
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2">
                    Message
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-32">
                    Tags
                  </th>
                  <th className="text-right text-xs text-muted-foreground font-medium px-4 py-2 w-24">
                    Count
                  </th>
                </tr>
              </thead>
              <tbody>
                {groupedSections
                  ? groupedSections.flatMap(({ value, items }) => [
                      <tr key={`group-${value}`} className="bg-muted/40">
                        <td
                          colSpan={6}
                          className="px-4 py-1.5 text-[11px] font-medium text-muted-foreground"
                        >
                          <span className="font-mono">{groupField}</span> = {" "}
                          <span className="font-mono text-foreground">{value}</span>{" "}
                          <span className="text-muted-foreground/70">({items.length})</span>
                        </td>
                      </tr>,
                      ...items.map(({ notification: n, tags }) => (
                        <NotificationRow
                          key={n.id}
                          notification={n}
                          tags={tags}
                          rules={rules}
                          isSelected={selected?.id === n.id}
                          formatTime={formatTime}
                          onClick={() => setSelected(selected?.id === n.id ? null : n)}
                        />
                      )),
                    ])
                  : visibleItems.map(({ notification: n, tags }) => (
                      <NotificationRow
                        key={n.id}
                        notification={n}
                        tags={tags}
                        rules={rules}
                        isSelected={selected?.id === n.id}
                        formatTime={formatTime}
                        onClick={() => setSelected(selected?.id === n.id ? null : n)}
                      />
                    ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <NotificationDetail
          notification={selected}
          tags={classifiedItems.find((i) => i.notification.id === selected.id)?.tags ?? []}
          rules={rules}
          formatTimestamp={formatTimestamp}
          onClose={() => setSelected(null)}
          onUpdate={(updated) => {
            mutate();
            setSelected(updated);
          }}
          alertStatesEnabled={appSettings?.alert_states_enabled ?? false}
        />
      )}
    </div>
  );
}

function TimeRangeControl({
  value,
  customAfter,
  customBefore,
  onChange,
  onCustomChange,
}: {
  value: Preset;
  customAfter: string;
  customBefore: string;
  onChange: (preset: Preset) => void;
  onCustomChange: (after: string, before: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [draftAfter, setDraftAfter] = useState(customAfter);
  const [draftBefore, setDraftBefore] = useState(customBefore);

  // Sync draft values whenever the popover opens
  useEffect(() => {
    if (open) {
      setDraftAfter(customAfter);
      setDraftBefore(customBefore);
    }
  }, [open, customAfter, customBefore]);

  const displayLabel = useMemo(() => {
    if (value === "custom" && (customAfter || customBefore)) {
      const fmt = (s: string) =>
        s
          ? new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric" })
          : "…";
      return `${fmt(customAfter)} – ${fmt(customBefore)}`;
    }
    return PRESETS.find((p) => p.value === value)?.label ?? "All time";
  }, [value, customAfter, customBefore]);

  const isActive = value !== "all";

  const handleClear = () => {
    onChange("all");
    onCustomChange("", "");
  };

  return (
    <div className="flex items-center gap-0.5 shrink-0">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            size="sm"
            variant="ghost"
            className={cn(
              "h-7 text-xs px-2 gap-1.5 shrink-0 max-w-[160px]",
              isActive
                ? "bg-primary/10 border border-primary/40 text-foreground hover:bg-primary/15"
                : "bg-input border border-input text-muted-foreground hover:text-foreground"
            )}
          >
            <Clock className="h-3 w-3 shrink-0" />
            <span className="truncate">{displayLabel}</span>
            <ChevronDown className="h-3 w-3 opacity-50 shrink-0" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-60 p-0 bg-card border-border" align="end">
          {/* Preset list */}
          <div className="p-1.5 space-y-0.5">
            {PRESETS.filter((p) => p.value !== "custom").map((p) => (
              <button
                key={p.value}
                onClick={() => {
                  onChange(p.value as Preset);
                  onCustomChange("", "");
                  setOpen(false);
                }}
                className={cn(
                  "w-full text-left px-2.5 py-1.5 text-xs rounded transition-colors",
                  value === p.value
                    ? "bg-primary/10 text-foreground font-medium"
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                )}
              >
                {p.label}
              </button>
            ))}
          </div>
          {/* Custom range — always visible, no extra click required */}
          <div className="border-t border-border p-3 space-y-2">
            <p className="text-[11px] font-medium text-muted-foreground">Custom range</p>
            <div className="space-y-1">
              <label htmlFor="time-range-from" className="text-[11px] text-muted-foreground">From</label>
              <Input
                id="time-range-from"
                name="time-range-from"
                type="datetime-local"
                value={draftAfter}
                onChange={(e) => setDraftAfter(e.target.value)}
                className="h-7 text-xs bg-input"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="time-range-to" className="text-[11px] text-muted-foreground">To</label>
              <Input
                id="time-range-to"
                name="time-range-to"
                type="datetime-local"
                value={draftBefore}
                onChange={(e) => setDraftBefore(e.target.value)}
                className="h-7 text-xs bg-input"
              />
            </div>
            <div className="flex justify-end gap-1.5">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 text-xs"
                onClick={() => {
                  handleClear();
                  setDraftAfter("");
                  setDraftBefore("");
                  setOpen(false);
                }}
              >
                Clear
              </Button>
              <Button
                size="sm"
                className="h-7 text-xs"
                disabled={!draftAfter && !draftBefore}
                onClick={() => {
                  onChange("custom");
                  onCustomChange(draftAfter, draftBefore);
                  setOpen(false);
                }}
              >
                Apply
              </Button>
            </div>
          </div>
        </PopoverContent>
      </Popover>

      {isActive && (
        <button
          onClick={handleClear}
          className="h-7 w-5 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors shrink-0"
          title="Clear time filter"
          aria-label="Clear time filter"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
}

function GroupByControl({
  groupField,
  groupValues,
  availableGroupFields,
  availableGroupValues,
  onFieldChange,
  onToggleValue,
  onSelectValues,
  onClearValues,
}: {
  groupField: string | null;
  groupValues: Set<string>;
  availableGroupFields: string[];
  availableGroupValues: string[];
  onFieldChange: (field: string | null) => void;
  onToggleValue: (value: string) => void;
  onSelectValues: (values: string[]) => void;
  onClearValues: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [valueSearch, setValueSearch] = useState("");
  const prevGroupField = useRef<string | null>(null);

  // Auto-open the value picker whenever a new field is selected
  useEffect(() => {
    if (groupField !== null && groupField !== prevGroupField.current) {
      setOpen(true);
    }
    if (groupField === null) setOpen(false);
    prevGroupField.current = groupField;
  }, [groupField]);

  const filteredValues = useMemo(() => {
    const term = valueSearch.trim().toLowerCase();
    if (!term) return availableGroupValues;
    return availableGroupValues.filter((v) => v.toLowerCase().includes(term));
  }, [availableGroupValues, valueSearch]);

  return (
    <div className="flex items-center gap-0.5 shrink-0">
      <span className="text-[11px] text-muted-foreground shrink-0 mr-1">Group by:</span>
      <Select
        value={groupField ?? "__none"}
        onValueChange={(v) => onFieldChange(v === "__none" ? null : v)}
      >
        <SelectTrigger
          className={cn(
            "h-7 w-36 text-xs shrink-0",
            groupField ? "bg-primary/10 border-primary/40 text-foreground" : "bg-input"
          )}
        >
          <SelectValue placeholder="Field…" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__none">None</SelectItem>
          {availableGroupFields.map((key) => (
            <SelectItem key={key} value={key}>
              {key}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {groupField && (
        <>
          {/* Values chip — click to reopen the picker */}
          <button
            onClick={() => setOpen(true)}
            className={cn(
              "flex items-center gap-1 h-7 px-2 rounded border text-xs transition-colors shrink-0",
              groupValues.size > 0
                ? "bg-primary/10 border-primary/40 text-foreground hover:bg-primary/15"
                : "bg-input border-input text-muted-foreground hover:text-foreground"
            )}
          >
            <ListFilter className="h-3 w-3 shrink-0" />
            {groupValues.size > 0
              ? `${groupValues.size} value${groupValues.size === 1 ? "" : "s"}`
              : "Select values…"}
          </button>

          {/* Clear group-by entirely */}
          <button
            onClick={() => { onFieldChange(null); onClearValues(); }}
            className="h-7 w-5 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors shrink-0"
            title="Clear group-by filter"
            aria-label="Clear group-by filter"
          >
            <X className="h-3 w-3" />
          </button>
        </>
      )}

      {/* Controlled dialog — no DialogTrigger needed */}
      <Dialog
        open={open}
        onOpenChange={(next) => {
          setOpen(next);
          if (!next) setValueSearch("");
        }}
      >
        <DialogContent className="max-w-md max-h-[80vh] flex flex-col bg-card border-border">
          <DialogHeader>
            <DialogTitle className="text-foreground">
              Group by <span className="font-mono">{groupField}</span>
            </DialogTitle>
          </DialogHeader>

          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={valueSearch}
              onChange={(e) => setValueSearch(e.target.value)}
              placeholder="Search values..."
              className="pl-8 h-8 text-sm bg-input"
              autoFocus
            />
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>
              {groupValues.size} of {availableGroupValues.length} selected
            </span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="hover:text-foreground transition-colors disabled:opacity-40 disabled:hover:text-muted-foreground"
                disabled={filteredValues.length === 0}
                onClick={() => onSelectValues(filteredValues)}
              >
                Select all
              </button>
              <button
                type="button"
                className="hover:text-foreground transition-colors disabled:opacity-40 disabled:hover:text-muted-foreground"
                disabled={groupValues.size === 0}
                onClick={onClearValues}
              >
                Clear all
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto rounded-md border border-border divide-y divide-border">
            {filteredValues.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                No matching values.
              </p>
            ) : (
              filteredValues.map((value) => (
                <label
                  key={value}
                  className="flex items-center gap-2.5 px-3 py-2 text-xs cursor-pointer hover:bg-muted/50 transition-colors"
                >
                  <Checkbox
                    checked={groupValues.has(value)}
                    onCheckedChange={() => onToggleValue(value)}
                  />
                  <span className="font-mono text-foreground truncate">{value}</span>
                </label>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function NotificationRow({
  notification: n,
  tags,
  rules,
  isSelected,
  formatTime,
  onClick,
}: {
  notification: NotificationOut;
  tags: string[];
  rules: ReturnType<typeof useTagRules>["rules"];
  isSelected: boolean;
  formatTime: (iso: string) => string;
  onClick: () => void;
}) {
  return (
    <tr
      onClick={onClick}
      className={cn(
        "cursor-pointer border-b border-border transition-colors",
        isSelected
          ? "bg-primary/10 text-foreground"
          : "hover:bg-muted/50 text-foreground"
      )}
    >
      <td className="px-4 py-2.5 font-mono text-xs text-muted-foreground whitespace-nowrap">
        {formatTime(n.received_at)}
      </td>
      <td className="px-4 py-2.5">
        <span
          className={cn(
            "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border uppercase tracking-wider",
            (() => {
              const colorKey = 
                n.severity === "critical" ? "red" :
                n.severity === "error" ? "orange" :
                n.severity === "warning" ? "yellow" :
                n.severity === "info" ? "blue" : "slate";
              const colors = TAG_COLOR_CLASSES[colorKey as keyof typeof TAG_COLOR_CLASSES];
              return `${colors.bg} ${colors.text} ${colors.border}`;
            })()
          )}
        >
          {n.severity}
        </span>
      </td>
      <td className="px-4 py-2.5 max-w-[8rem]">
        {n.sender_name ? (
          <Badge variant="secondary" className="text-xs font-normal truncate max-w-full">
            {n.sender_name}
          </Badge>
        ) : (
          <span className="text-muted-foreground text-xs">—</span>
        )}
      </td>
      <td className="px-4 py-2.5 max-w-0 w-full">
        {n.title && (
          <span className="font-medium text-foreground mr-2">{n.title}</span>
        )}
        <span className="text-muted-foreground text-xs line-clamp-1">{n.message}</span>
      </td>
      <td className="px-4 py-2.5">
        <div className="flex flex-wrap gap-1">
          {tags.map((tag) => {
            const rule = rules.find((r) => r.name === tag);
            const colors = rule ? TAG_COLOR_CLASSES[rule.color] : TAG_COLOR_CLASSES.slate;
            return (
              <span
                key={tag}
                className={cn(
                  "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border",
                  colors.bg,
                  colors.text,
                  colors.border
                )}
              >
                {tag}
              </span>
            );
          })}
        </div>
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-muted-foreground">
        {n.occurrences > 1 ? (
          <Badge variant="outline" className="text-[10px]">
            {n.occurrences}
          </Badge>
        ) : (
          "—"
        )}
      </td>
    </tr>
  );
}
