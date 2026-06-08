"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import useSWR from "swr";
import { Search, ChevronLeft, ChevronRight, RefreshCw, Inbox, X, ListFilter, Clock } from "lucide-react";
import { fetchNotifications, notificationsKey } from "@/lib/api";
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { NotificationDetail } from "@/components/notification-detail";
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

const PAGE_SIZE = 20;
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
  const [serverPage, setServerPage] = useState(1);
  const [clientPage, setClientPage] = useState(1);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<NotificationOut | null>(null);
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [groupField, setGroupField] = useState<string | null>(null);
  const [groupValues, setGroupValues] = useState<Set<string>>(new Set());
  // Time range filter
  const [timeRange, setTimeRange] = useState<Preset>("all");
  const [customAfter, setCustomAfter] = useState("");
  const [customBefore, setCustomBefore] = useState("");
  // Bumped by the Refresh button so that preset "after" times recompute to now
  const [refreshNonce, setRefreshNonce] = useState(0);

  const { formatTimestamp, formatTime } = usePreferences();
  const { rules, classify } = useTagRules();

  // Are any client-side filters active?
  const hasExclude = useMemo(() => rules.some((r) => r.enabled && r.exclude), [rules]);
  const groupingActive = groupField !== null && groupValues.size > 0;
  const filtersActive = hasExclude || activeTag !== null || groupingActive;

  // When filters are active we fetch a large page so client-side filtering
  // has enough raw material. When filters are off, use normal server pagination.
  const fetchSize = filtersActive ? FILTERED_FETCH_SIZE : PAGE_SIZE;
  const fetchPage = filtersActive ? serverPage : serverPage;

  // Resolve the currently selected time range to ISO strings. Depends on
  // refreshNonce so clicking Refresh slides the preset window to "now".
  const { after: timeAfter, before: timeBefore } = useMemo(
    () => resolveTimeRange(timeRange, customAfter, customBefore),
    // refreshNonce intentionally included so preset windows recompute on Refresh
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [timeRange, customAfter, customBefore, refreshNonce]
  );

  const swrKey = useMemo(
    () => notificationsKey(fetchPage, query, fetchSize, timeAfter, timeBefore),
    [fetchPage, query, fetchSize, timeAfter, timeBefore]
  );

  const { data, isLoading, mutate } = useSWR(swrKey, fetchNotifications, {
    refreshInterval: 30_000,
  });

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
  const clientPageCount = Math.max(1, Math.ceil(groupFilteredItems.length / PAGE_SIZE));

  // If the current client page exceeds available pages (e.g. filter was just
  // enabled and fewer items are visible), reset to page 1.
  useEffect(() => {
    if (clientPage > clientPageCount) setClientPage(1);
  }, [clientPage, clientPageCount]);

  // When filters are active we slice groupFilteredItems for display;
  // otherwise the server already returned exactly one page worth.
  const visibleItems = filtersActive
    ? groupFilteredItems.slice((clientPage - 1) * PAGE_SIZE, clientPage * PAGE_SIZE)
    : groupFilteredItems;

  // Pagination metadata shown in the UI
  // When filters are active: client-side page over filtered results + a
  // "load more from server" button when we've exhausted the current fetch.
  const displayPage = filtersActive ? clientPage : data?.page ?? 1;
  const displayPages = filtersActive
    ? clientPageCount
    : data?.pages ?? 1;
  const displayTotal = filtersActive ? groupFilteredItems.length : data?.total ?? 0;
  // True when filters are active, we've consumed all locally-fetched items,
  // and the server has more pages.
  const serverHasMore =
    filtersActive &&
    clientPage >= clientPageCount &&
    data != null &&
    serverPage < data.pages;

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setServerPage(1);
      setClientPage(1);
      setQuery(search.trim());
    },
    [search]
  );

  const handleTimeRangeChange = useCallback((preset: Preset) => {
    setTimeRange(preset);
    setServerPage(1);
    setClientPage(1);
  }, []);

  const handleClearSearch = () => {
    setSearch("");
    setQuery("");
    setServerPage(1);
    setClientPage(1);
  };

  const handlePrev = () => {
    if (filtersActive) {
      if (clientPage > 1) {
        setClientPage((p) => p - 1);
      } else if (serverPage > 1) {
        setServerPage((p) => p - 1);
        setClientPage(1);
      }
    } else {
      setServerPage((p) => Math.max(1, p - 1));
    }
  };

  const handleNext = () => {
    if (filtersActive) {
      if (clientPage < clientPageCount) {
        setClientPage((p) => p + 1);
      } else if (serverHasMore) {
        // Fetch the next server page; reset client page to 1 within new fetch
        setServerPage((p) => p + 1);
        setClientPage(1);
      }
    } else {
      setServerPage((p) => p + 1);
    }
  };

  const canGoPrev = filtersActive
    ? clientPage > 1 || serverPage > 1
    : serverPage > 1;
  const canGoNext = filtersActive
    ? clientPage < clientPageCount || serverHasMore
    : serverPage < (data?.pages ?? 1);

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
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search notifications..."
                className="pl-8 h-8 text-sm bg-input"
              />
            </div>
            <Button type="submit" size="sm" variant="secondary" className="h-8">
              Search
            </Button>
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
          {data && (
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {filtersActive
                ? `${displayTotal.toLocaleString()} visible`
                : `${data.total.toLocaleString()} total`}
            </span>
          )}
        </div>

        {/* Filter bar: always visible — tag chips on the left, time range + group-by on the right */}
        <div className="flex items-center gap-1.5 px-4 py-2 border-b border-border bg-card/30 overflow-x-auto">
          {enabledTags.length > 0 && (
            <>
              <span className="text-[11px] text-muted-foreground shrink-0 mr-1">Filter:</span>
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
                  className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground shrink-0"
                >
                  <X className="h-3 w-3" />
                  Clear filter
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
              setServerPage(1);
              setClientPage(1);
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
                setServerPage(1);
                setClientPage(1);
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
                  onClick={() => { setServerPage((p) => p + 1); setClientPage(1); }}
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
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-32">
                    Sender
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2">
                    Message
                  </th>
                  <th className="text-left text-xs text-muted-foreground font-medium px-4 py-2 w-32">
                    Tags
                  </th>
                </tr>
              </thead>
              <tbody>
                {groupedSections
                  ? groupedSections.flatMap(({ value, items }) => [
                      <tr key={`group-${value}`} className="bg-muted/40">
                        <td
                          colSpan={4}
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

        {/* Pagination */}
        {(displayPages > 1 || serverHasMore) && (
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-border bg-card/50 text-xs text-muted-foreground">
            <span>
              Page {displayPage} of {displayPages}
              {serverHasMore && "+"}
            </span>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                disabled={!canGoPrev}
                onClick={handlePrev}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                disabled={!canGoNext}
                onClick={handleNext}
              >
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Detail panel */}
      {selected && (
        <NotificationDetail
          notification={selected}
          tags={classifiedItems.find((i) => i.notification.id === selected.id)?.tags ?? []}
          rules={rules}
          formatTimestamp={formatTimestamp}
          onClose={() => setSelected(null)}
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
  const [customOpen, setCustomOpen] = useState(false);
  const [draftAfter, setDraftAfter] = useState(customAfter);
  const [draftBefore, setDraftBefore] = useState(customBefore);

  const handlePresetChange = (v: string) => {
    if (v === "custom") {
      setDraftAfter(customAfter);
      setDraftBefore(customBefore);
      setCustomOpen(true);
      onChange("custom");
    } else {
      onChange(v as Preset);
    }
  };

  const applyCustom = () => {
    onCustomChange(draftAfter, draftBefore);
    setCustomOpen(false);
  };

  const label = PRESETS.find((p) => p.value === value)?.label ?? "All time";
  const isActive = value !== "all";

  return (
    <div className="flex items-center gap-1 shrink-0">
      <Clock className="h-3 w-3 text-muted-foreground shrink-0" />
      <Select value={value} onValueChange={handlePresetChange}>
        <SelectTrigger
          className={cn(
            "h-7 w-36 text-xs shrink-0",
            isActive ? "bg-primary/10 border-primary/40 text-foreground" : "bg-input"
          )}
        >
          <SelectValue>{label}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {PRESETS.map((p) => (
            <SelectItem key={p.value} value={p.value}>
              {p.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {value === "custom" && (
        <Popover open={customOpen} onOpenChange={setCustomOpen}>
          <PopoverTrigger asChild>
            <Button
              size="sm"
              variant={customAfter || customBefore ? "secondary" : "ghost"}
              className="h-7 px-2 text-xs shrink-0"
            >
              {customAfter || customBefore ? "Edit range" : "Set range…"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-72 p-4 bg-card border-border" align="end">
            <div className="space-y-3">
              <p className="text-xs font-medium text-foreground">Custom time range</p>
              <div className="space-y-1.5">
                <label className="text-[11px] text-muted-foreground">From</label>
                <Input
                  type="datetime-local"
                  value={draftAfter}
                  onChange={(e) => setDraftAfter(e.target.value)}
                  className="h-8 text-xs bg-input"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[11px] text-muted-foreground">To</label>
                <Input
                  type="datetime-local"
                  value={draftBefore}
                  onChange={(e) => setDraftBefore(e.target.value)}
                  className="h-8 text-xs bg-input"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => {
                    setDraftAfter("");
                    setDraftBefore("");
                    onCustomChange("", "");
                    setCustomOpen(false);
                  }}
                >
                  Clear
                </Button>
                <Button size="sm" className="h-7 text-xs" onClick={applyCustom}>
                  Apply
                </Button>
              </div>
            </div>
          </PopoverContent>
        </Popover>
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

  const filteredValues = useMemo(() => {
    const term = valueSearch.trim().toLowerCase();
    if (!term) return availableGroupValues;
    return availableGroupValues.filter((v) => v.toLowerCase().includes(term));
  }, [availableGroupValues, valueSearch]);

  return (
    <div className="flex items-center gap-1.5 shrink-0">
      <span className="text-[11px] text-muted-foreground shrink-0">Group by:</span>
      <Select
        value={groupField ?? "__none"}
        onValueChange={(v) => onFieldChange(v === "__none" ? null : v)}
      >
        <SelectTrigger className="h-7 w-40 text-xs bg-input shrink-0">
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
        <Dialog
          open={open}
          onOpenChange={(next) => {
            setOpen(next);
            if (!next) setValueSearch("");
          }}
        >
          <DialogTrigger asChild>
            <Button size="sm" variant="secondary" className="h-7 px-2.5 text-xs gap-1.5 shrink-0">
              <ListFilter className="h-3 w-3" />
              {groupValues.size > 0
                ? `${groupValues.size} value${groupValues.size === 1 ? "" : "s"}`
                : "Select values…"}
            </Button>
          </DialogTrigger>
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
      )}
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
    </tr>
  );
}
