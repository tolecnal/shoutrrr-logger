"use client";

import useSWR from "swr";
import { useMemo } from "react";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";
import { fetchAdminPluginUsageStats, fetchUserPluginUsageStats } from "@/lib/api";
import type { PluginUsageStat } from "@/lib/types";
import { useAuth } from "@/lib/auth-context";

export function PluginStatsPanel() {
  const { user } = useAuth();
  
  const fetcher = user?.role === "admin" ? fetchAdminPluginUsageStats : fetchUserPluginUsageStats;

  const { data, isLoading, error } = useSWR<PluginUsageStat[]>(
    ["/plugins/stats/usage", user?.role],
    () => fetcher(),
    { refreshInterval: 60_000 }
  );

  const uniquePlugins = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.map(d => d.plugin_id))).sort();
  }, [data]);

  const allChartsData = useMemo(() => {
    if (!data) return {};
    const map: Record<string, any[]> = {};
    const pluginsToProcess = [...uniquePlugins, "all"];
    
    pluginsToProcess.forEach(pid => {
      const filtered = pid === "all" ? data : data.filter(d => d.plugin_id === pid);
      const grouped = filtered.reduce((acc, stat) => {
        const dateStr = stat.date.substring(0, 10);
        if (!acc[dateStr]) acc[dateStr] = { date: dateStr, success: 0, error: 0, total_duration_ms: 0 };
        acc[dateStr].success += stat.success_count;
        acc[dateStr].error += stat.error_count;
        acc[dateStr].total_duration_ms += stat.total_duration_ms || 0;
        return acc;
      }, {} as Record<string, { date: string; success: number; error: number; total_duration_ms: number }>);
      
      map[pid] = Object.values(grouped).map(g => ({
        ...g,
        avg_response_time: (g.success + g.error) > 0 ? Math.round(g.total_duration_ms / (g.success + g.error)) : 0
      })).sort((a, b) => a.date.localeCompare(b.date));
    });
    
    return map;
  }, [data, uniquePlugins]);

  const pluginBreakdown = useMemo(() => {
    if (!data) return [];
    
    const grouped = data.reduce((acc, stat) => {
      const type = stat.user_id ? "User" : "Global (Admin)";
      const key = `${stat.plugin_id}-${type}`;
      if (!acc[key]) {
        acc[key] = { plugin_id: stat.plugin_id, type, success: 0, error: 0, total_duration_ms: 0 };
      }
      acc[key].success += stat.success_count;
      acc[key].error += stat.error_count;
      acc[key].total_duration_ms += stat.total_duration_ms || 0;
      return acc;
    }, {} as Record<string, { plugin_id: string; type: string; success: number; error: number; total_duration_ms: number }>);
    
    return Object.values(grouped).map(g => ({
      ...g,
      avg_response_time: (g.success + g.error) > 0 ? Math.round(g.total_duration_ms / (g.success + g.error)) : 0
    })).sort((a, b) => {
      const comp = a.plugin_id.localeCompare(b.plugin_id);
      if (comp !== 0) return comp;
      return a.type.localeCompare(b.type);
    });
  }, [data]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Plugin Usage Statistics</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Overview of plugin notification dispatch results.
        </p>
      </div>

      {isLoading ? (
        <div className="h-52 flex items-center justify-center text-sm text-muted-foreground rounded-lg border border-border bg-card p-5">
          Loading...
        </div>
      ) : error ? (
        <div className="h-52 flex items-center justify-center text-sm text-destructive rounded-lg border border-border bg-card p-5">
          Failed to load stats
        </div>
      ) : uniquePlugins.length === 0 ? (
        <div className="h-52 flex items-center justify-center text-sm text-muted-foreground rounded-lg border border-border bg-card p-5">
          No plugin usage data yet
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[...uniquePlugins, "all"].map(pid => {
            const chartData = allChartsData[pid] || [];
            return (
              <div key={pid} className="rounded-lg border border-border bg-card p-5">
                <h2 className="text-sm font-medium text-foreground mb-4 capitalize">
                  {pid === "all" ? "Average Over All Plugins" : pid}
                </h2>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
                      <XAxis 
                        dataKey="date" 
                        tickFormatter={(val) => format(parseISO(val), "MMM d")}
                        tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                        tickLine={false}
                        axisLine={false}
                        dy={10}
                      />
                      <YAxis 
                        yAxisId="left"
                        tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                        tickLine={false}
                        axisLine={false}
                        dx={-10}
                        allowDecimals={false}
                      />
                      <YAxis 
                        yAxisId="right"
                        orientation="right"
                        tick={{ fontSize: 11, fill: "var(--muted-foreground)" }}
                        tickLine={false}
                        axisLine={false}
                        dx={10}
                        tickFormatter={(val) => `${val}ms`}
                      />
                      <Tooltip 
                        cursor={{ fill: "var(--muted)", opacity: 0.2 }}
                        contentStyle={{ 
                          borderRadius: "6px", 
                          border: "1px solid var(--border)",
                          backgroundColor: "var(--card)",
                          fontSize: "12px",
                          color: "var(--foreground)"
                        }}
                        labelFormatter={(label) => format(parseISO(label as string), "EEE, MMM d")}
                      />
                      <Legend iconType="circle" wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
                      <Bar yAxisId="left" name="Success" dataKey="success" stackId="a" fill="var(--primary)" radius={[0, 0, 4, 4]} maxBarSize={40} />
                      <Bar yAxisId="left" name="Error" dataKey="error" stackId="a" fill="var(--destructive)" radius={[4, 4, 0, 0]} maxBarSize={40} />
                      <Line yAxisId="right" name="Avg Response Time (ms)" type="monotone" dataKey="avg_response_time" stroke="var(--chart-3, #4f46e5)" strokeWidth={2} dot={{ r: 3 }} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="rounded-lg border border-border bg-card overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h2 className="text-sm font-medium text-foreground">
            Plugin Breakdown
          </h2>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-muted-foreground bg-muted/50 uppercase">
              <tr>
                <th className="px-5 py-3 font-medium">Plugin</th>
                <th className="px-5 py-3 font-medium">Profile Type</th>
                <th className="px-5 py-3 font-medium text-right">Success</th>
                <th className="px-5 py-3 font-medium text-right">Error</th>
                <th className="px-5 py-3 font-medium text-right">Avg Response Time</th>
              </tr>
            </thead>
            <tbody>
              {pluginBreakdown.map((item) => (
                <tr key={`${item.plugin_id}-${item.type}`} className="border-b border-border last:border-0 hover:bg-muted/30">
                  <td className="px-5 py-3 font-medium text-foreground capitalize">
                    {item.plugin_id}
                  </td>
                  <td className="px-5 py-3 text-muted-foreground">
                    {item.type}
                  </td>
                  <td className="px-5 py-3 text-right">
                    {item.success}
                  </td>
                  <td className="px-5 py-3 text-right text-destructive">
                    {item.error > 0 ? item.error : "-"}
                  </td>
                  <td className="px-5 py-3 text-right text-muted-foreground">
                    {item.avg_response_time > 0 ? `${item.avg_response_time}ms` : "-"}
                  </td>
                </tr>
              ))}
              {pluginBreakdown.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-5 py-8 text-center text-muted-foreground">
                    No data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
