"use client";

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
import { Activity, BarChart2, CalendarDays, Clock } from "lucide-react";
import { fetchStats } from "@/lib/api";
import type { NotificationStats } from "@/lib/types";
import { cn } from "@/lib/utils";

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
  value: number | undefined;
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
        <p className="text-2xl font-semibold text-foreground tabular-nums">
          {value === undefined ? "—" : value.toLocaleString()}
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Custom tooltip for the area chart
// ---------------------------------------------------------------------------
function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number }[];
  label?: string;
}) {
  if (!active || !payload?.length || !label) return null;
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2 shadow-md text-xs">
      <p className="text-muted-foreground mb-0.5">
        {format(parseISO(label), "EEE, MMM d")}
      </p>
      <p className="font-semibold text-foreground">
        {payload[0].value.toLocaleString()} notification{payload[0].value !== 1 ? "s" : ""}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel
// ---------------------------------------------------------------------------
export function StatsPanel() {
  const { data, isLoading, error } = useSWR<NotificationStats>(
    "/notifications/stats",
    () => fetchStats(30),
    { refreshInterval: 60_000 }
  );

  const last30 = data?.by_day.reduce((sum, d) => sum + d.count, 0) ?? undefined;

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-foreground">Statistics</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Notification activity overview
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Total notifications"
          value={data?.total}
          icon={BarChart2}
        />
        <StatCard
          label="Today"
          value={data?.today}
          icon={Clock}
          accent={!!data?.today}
        />
        <StatCard
          label="This week"
          value={data?.this_week}
          icon={CalendarDays}
        />
        <StatCard
          label="Last 30 days"
          value={last30}
          icon={Activity}
        />
      </div>

      {/* Area chart */}
      <div className="rounded-lg border border-border bg-card p-5">
        <h2 className="text-sm font-medium text-foreground mb-4">
          Notifications over time
          <span className="ml-1.5 text-xs font-normal text-muted-foreground">(last 30 days)</span>
        </h2>

        {isLoading ? (
          <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
            Loading…
          </div>
        ) : error ? (
          <div className="h-52 flex items-center justify-center text-sm text-destructive">
            Failed to load stats
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data?.by_day ?? []} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border))"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                tickFormatter={(v: string) => format(parseISO(v), "MMM d")}
                interval={Math.ceil((data?.by_day.length ?? 30) / 6) - 1}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                allowDecimals={false}
              />
              <Tooltip content={<ChartTooltip />} />
              <Area
                type="monotone"
                dataKey="count"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                fill="url(#areaGradient)"
                dot={false}
                activeDot={{ r: 4, fill: "hsl(var(--primary))", strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Top senders */}
      {data && data.top_senders.length > 0 && (
        <div className="rounded-lg border border-border bg-card p-5">
          <h2 className="text-sm font-medium text-foreground mb-4">Top senders</h2>
          <div className="space-y-2">
            {data.top_senders.map((s, i) => {
              const max = data.top_senders[0]?.count ?? 1;
              const pct = Math.round((s.count / max) * 100);
              return (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <span className="w-5 text-right text-xs text-muted-foreground shrink-0">
                    {i + 1}
                  </span>
                  <span className="w-40 truncate text-foreground font-mono text-xs shrink-0">
                    {s.sender ?? "(unknown)"}
                  </span>
                  <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary/60 transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground tabular-nums w-12 text-right shrink-0">
                    {s.count.toLocaleString()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
