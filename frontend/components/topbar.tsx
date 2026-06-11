"use client";

import Link from "next/link";
import { Bell } from "lucide-react";
import useSWR from "swr";
import { fetchAlerts } from "@/lib/api";

export function Topbar() {
  const { data: alerts } = useSWR("/alerts", fetchAlerts, { refreshInterval: 10000 });
  const unreadCount = alerts?.filter(a => !a.is_read).length || 0;

  return (
    <div className="hidden md:flex h-14 border-b border-border items-center justify-end px-6 sticky top-0 bg-background/95 backdrop-blur z-10">
      <Link href="/alerts" className="relative text-muted-foreground hover:text-foreground flex items-center justify-center p-2 rounded-full hover:bg-accent transition-colors">
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 flex h-2 w-2 rounded-full bg-destructive" />
        )}
      </Link>
    </div>
  );
}
