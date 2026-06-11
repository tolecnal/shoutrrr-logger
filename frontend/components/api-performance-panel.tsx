"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";
import { Activity, AlertTriangle, Clock, Gauge, Search } from "lucide-react";
import { fetchApiPerformance } from "@/lib/api";
import type { ApiPerformanceStats } from "@/lib/types";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const METHOD_COLORS: Record<string, string> = {
  GET: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  POST: "bg-green-500/15 text-green-700 dark:text-green-400",
  PUT: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  PATCH: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  DELETE: "bg-red-500/15 text-red-700 dark:text-red-400",
};

const WINDOWS = [
  { label: "Last 1h", value: 1 },
  { label: "Last 6h", value: 6 },
  { label: "Last 24h", value: 24 },
  { label: "Last 48h", value: 48 },
  { label: "Last 7 days", value: 168 },
];

function msClass(ms: number): string {
  if (ms < 100) return "text-green-600 dark:text-green-400";
  if (ms < 500) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

function errClass(rate: number): string {
  if (rate === 0) return "text-muted-foreground";
  if (rate < 5) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

function fmtMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(0)}ms`;
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------
function StatCard({
  label,
  value,
  icon: Icon,
  accent,
}: {
  label: string;
  value: string | undefined;
  icon: React.ComponentType<{ className?: string }>;
  accent?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-card px-5 py-4 flex items-center gap-4",
        accent && "border-primary/30 bg-primary/5"
      )}
    >
      <div
        className={cn(
          "flex h-10 w-10 items-center justify-center rounded-md shrink-0",
          accent ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"
        )}
      >
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] text-muted-foreground uppercase tracking-wide truncate">{label}</p>
        <p className="text-2xl font-semibold text-foreground tabular-nums">{value ?? "—"}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chart tooltip
// ---------------------------------------------------------------------------
function ChartTooltip({
  active,
  payload,
  label,
  windowHours,
}: {
  active?: boolean;
  payload?: { value: number; payload: { avg_ms: number } }[];
  label?: string;
  windowHours: number;
}) {
  if (!active || !payload?.length || !label) return null;
  const ts = parseISO(label);
  const timeStr =
    windowHours <= 24
      ? format(ts, "HH:mm")
      : format(ts, "MMM d HH:mm");
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 shadow-md text-xs space-y-0.5">
      <p className="text-muted-foreground">{timeStr}</p>
      <p className="font-semibold text-foreground">
        {payload[0].value.toLocaleString()} request{payload[0].value !== 1 ? "s" : ""}
      </p>
      <p className="text-muted-foreground">
        avg {fmtMs(payload[0].payload.avg_ms)}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------
export function ApiPerformancePanel() {
  const [windowHours, setWindowHours] = useState(24);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState<"endpoint" | "requests" | "avg" | "p95" | "error">("requests");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  const { data, isLoading, error } = useSWR<ApiPerformanceStats>(
    ["/admin/performance", windowHours],
    ([, h]) => fetchApiPerformance(h as number),
    { refreshInterval: 30_000 }
  );

  const filteredAndSortedEndpoints = useMemo(() => {
    if (!data) return [];
    
    let result = data.by_endpoint;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(ep => ep.path.toLowerCase().includes(q) || ep.method.toLowerCase().includes(q));
    }

    return [...result].sort((a, b) => {
      let aVal: any, bVal: any;
      switch (sortField) {
        case "endpoint":
          aVal = `${a.method} ${a.path}`;
          bVal = `${b.method} ${b.path}`;
          break;
        case "requests":
          aVal = a.request_count;
          bVal = b.request_count;
          break;
        case "avg":
          aVal = a.avg_ms;
          bVal = b.avg_ms;
          break;
        case "p95":
          aVal = a.p95_ms;
          bVal = b.p95_ms;
          break;
        case "error":
          aVal = a.error_rate;
          bVal = b.error_rate;
          break;
      }
      
      if (aVal < bVal) return sortDirection === "asc" ? -1 : 1;
      if (aVal > bVal) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [data, searchQuery, sortField, sortDirection]);

  const handleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection(field === "endpoint" ? "asc" : "desc");
    }
  };

  const renderSortIcon = (field: typeof sortField) => {
    if (sortField !== field) return <span className="ml-1 text-[10px] opacity-0 group-hover:opacity-40">↕</span>;
    return <span className="ml-1 text-[10px]">{sortDirection === "asc" ? "▲" : "▼"}</span>;
  };



  const windowLabel = WINDOWS.find((w) => w.value === windowHours)?.label ?? `Last ${windowHours}h`;

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-foreground">API Performance</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Request latency and error rates across all endpoints
          </p>
        </div>
        <select
          value={windowHours}
          onChange={(e) => setWindowHours(Number(e.target.value))}
          className="rounded-md border border-border bg-card text-sm text-foreground px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
        >
          {WINDOWS.map((w) => (
            <option key={w.value} value={w.value}>
              {w.label}
            </option>
          ))}
        </select>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Total requests"
          value={data ? data.total_requests.toLocaleString() : undefined}
          icon={Activity}
        />
        <StatCard
          label="Avg response time"
          value={data ? fmtMs(data.avg_ms) : undefined}
          icon={Clock}
        />
        <StatCard
          label="P95 response time"
          value={data ? fmtMs(data.p95_ms) : undefined}
          icon={Gauge}
        />
        <StatCard
          label="Server error rate"
          value={data ? `${data.error_rate.toFixed(2)}%` : undefined}
          icon={AlertTriangle}
          accent={!!data && data.error_rate > 0}
        />
      </div>

      {/* Requests-over-time chart */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h2 className="text-sm font-medium text-foreground mb-4">
          Requests over time
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">
            ({windowLabel}, per hour)
          </span>
        </h2>

        {isLoading ? (
          <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : error ? (
          <div className="h-52 flex items-center justify-center text-sm text-destructive">
            Failed to load performance data
          </div>
        ) : !data || data.by_hour.length === 0 ? (
          <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
            No data for this window yet
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart
              data={data.by_hour}
              margin={{ top: 4, right: 4, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="perfAreaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--chart-1)" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="var(--chart-1)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis
                dataKey="time"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                tickFormatter={(v: string) =>
                  windowHours <= 24
                    ? format(parseISO(v), "HH:mm")
                    : format(parseISO(v), "MMM d HH:mm")
                }
                interval={Math.max(0, Math.ceil(data.by_hour.length / 6) - 1)}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
                allowDecimals={false}
              />
              <Tooltip content={<ChartTooltip windowHours={windowHours} />} />
              <Area
                type="monotone"
                dataKey="count"
                stroke="var(--chart-1)"
                strokeWidth={2}
                fill="url(#perfAreaGradient)"
                dot={false}
                activeDot={{ r: 4, fill: "var(--chart-1)", strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Endpoint performance table */}
      {data && data.by_endpoint.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-5">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <h2 className="text-sm font-medium text-foreground">
              Endpoint breakdown
              <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                ({windowLabel})
              </span>
            </h2>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search endpoints..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 rounded-md border border-border bg-transparent pl-8 pr-3 text-xs focus:outline-none focus:ring-1 focus:ring-primary w-[200px]"
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground select-none">
                  <th className="text-left py-2 pr-4 font-medium w-full cursor-pointer group" onClick={() => handleSort("endpoint")}>
                    Endpoint {renderSortIcon("endpoint")}
                  </th>
                  <th className="text-right py-2 px-3 font-medium whitespace-nowrap cursor-pointer group" onClick={() => handleSort("requests")}>
                    Requests {renderSortIcon("requests")}
                  </th>
                  <th className="text-right py-2 px-3 font-medium whitespace-nowrap cursor-pointer group" onClick={() => handleSort("avg")}>
                    Avg {renderSortIcon("avg")}
                  </th>
                  <th className="text-right py-2 px-3 font-medium whitespace-nowrap cursor-pointer group" onClick={() => handleSort("p95")}>
                    P95 {renderSortIcon("p95")}
                  </th>
                  <th className="text-right py-2 pl-3 font-medium whitespace-nowrap cursor-pointer group" onClick={() => handleSort("error")}>
                    Error % {renderSortIcon("error")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {filteredAndSortedEndpoints.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-muted-foreground">
                      No endpoints match your search.
                    </td>
                  </tr>
                ) : (
                  filteredAndSortedEndpoints.map((ep, i) => (
                  <tr
                    key={i}
                    className="border-b border-border/50 last:border-0 hover:bg-muted/30 transition-colors"
                  >
                    <td className="py-2.5 pr-4">
                      <div className="flex items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            "inline-flex items-center justify-center rounded px-1.5 py-0.5 text-[10px] font-semibold shrink-0 w-14 text-center",
                            METHOD_COLORS[ep.method] ?? "bg-muted text-muted-foreground"
                          )}
                        >
                          {ep.method}
                        </span>
                        <span
                          className="font-mono text-foreground truncate"
                          title={ep.path}
                        >
                          {ep.path}
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-right tabular-nums text-foreground">
                      {ep.request_count.toLocaleString()}
                    </td>
                    <td className={cn("py-2.5 px-3 text-right tabular-nums font-medium", msClass(ep.avg_ms))}>
                      {fmtMs(ep.avg_ms)}
                    </td>
                    <td className={cn("py-2.5 px-3 text-right tabular-nums font-medium", msClass(ep.p95_ms))}>
                      {fmtMs(ep.p95_ms)}
                    </td>
                    <td className={cn("py-2.5 pl-3 text-right tabular-nums font-medium", errClass(ep.error_rate))}>
                      {ep.error_count > 0
                        ? `${ep.error_rate.toFixed(1)}% (${ep.error_count})`
                        : "0%"}
                    </td>
                  </tr>
                )))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {data && data.total_requests === 0 && (
        <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
          No API requests recorded in this window yet. Data appears as traffic comes in.
        </div>
      )}
    </div>
  );
}
