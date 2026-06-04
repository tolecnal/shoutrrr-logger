"use client";

import { useState, useCallback, useMemo, useEffect } from "react";
import useSWR from "swr";
import { Search, ChevronLeft, ChevronRight, RefreshCw, Inbox, X } from "lucide-react";
import { fetchNotifications, notificationsKey } from "@/lib/api";
import type { NotificationOut } from "@/lib/types";
import { usePreferences } from "@/lib/use-preferences";
import { useTagRules, isExcluded, TAG_COLOR_CLASSES } from "@/lib/use-tag-rules";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { NotificationDetail } from "@/components/notification-detail";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;
// When filters are active we need a larger server page so that after
// client-side filtering we still have enough rows to fill the view.
const FILTERED_FETCH_SIZE = 100;

export function NotificationLog() {
  const [serverPage, setServerPage] = useState(1);
  const [clientPage, setClientPage] = useState(1);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<NotificationOut | null>(null);
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const { formatTimestamp, formatTime } = usePreferences();
  const { rules, classify } = useTagRules();

  // Are any client-side filters active?
  const hasExclude = useMemo(() => rules.some((r) => r.enabled && r.exclude), [rules]);
  const filtersActive = hasExclude || activeTag !== null;

  // When filters are active we fetch a large page so client-side filtering
  // has enough raw material. When filters are off, use normal server pagination.
  const fetchSize = filtersActive ? FILTERED_FETCH_SIZE : PAGE_SIZE;
  const fetchPage = filtersActive ? serverPage : serverPage;

  const swrKey = useMemo(
    () => notificationsKey(fetchPage, query, fetchSize),
    [fetchPage, query, fetchSize]
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

  // Client-side pagination over filteredItems when filters are active
  const clientPageCount = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));

  // If the current client page exceeds available pages (e.g. filter was just
  // enabled and fewer items are visible), reset to page 1.
  useEffect(() => {
    if (clientPage > clientPageCount) setClientPage(1);
  }, [clientPage, clientPageCount]);

  // When filters are active we slice filteredItems for display; otherwise
  // the server already returned exactly one page worth.
  const visibleItems = filtersActive
    ? filteredItems.slice((clientPage - 1) * PAGE_SIZE, clientPage * PAGE_SIZE)
    : filteredItems;

  // Pagination metadata shown in the UI
  // When filters are active: client-side page over filtered results + a
  // "load more from server" button when we've exhausted the current fetch.
  const displayPage = filtersActive ? clientPage : data?.page ?? 1;
  const displayPages = filtersActive
    ? clientPageCount
    : data?.pages ?? 1;
  const displayTotal = filtersActive ? filteredItems.length : data?.total ?? 0;
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
            onClick={() => mutate()}
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

        {/* Tag filter bar */}
        {enabledTags.length > 0 && (
          <div className="flex items-center gap-1.5 px-4 py-2 border-b border-border bg-card/30 overflow-x-auto">
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
                className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground shrink-0"
              >
                <X className="h-3 w-3" />
                Clear filter
              </button>
            )}
          </div>
        )}

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
                {visibleItems.map(({ notification: n, tags }) => (
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
