"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart2, Bell, Inbox, Info, LogIn, LogOut, Settings, User } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PreferencesDialog } from "@/components/preferences-dialog";
import { Topbar } from "@/components/topbar";
import useSWR from "swr";
import { fetchAlerts } from "@/lib/api";

const navItems = [
  { href: "/log", label: "Notification Log", icon: Inbox, roles: ["viewer", "admin"] },
  { href: "/stats", label: "Statistics", icon: BarChart2, roles: ["admin"] },
  { href: "/performance", label: "API Performance", icon: Activity, roles: ["admin"] },
  { href: "/admin", label: "Admin", icon: Settings, roles: ["admin"] },
  { href: "/about", label: "About", icon: Info, roles: ["viewer", "admin"] },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const pathname = usePathname();
  const { data: alerts } = useSWR(user ? "/alerts" : null, fetchAlerts, { refreshInterval: 10000 });
  const unreadCount = alerts?.filter((a) => a.state === "unread").length || 0;

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="hidden md:flex w-56 flex-col border-r border-border bg-sidebar shrink-0 sticky top-0 h-screen overflow-y-auto">
        {/* Logo */}
        <div className="flex items-center gap-2 px-5 py-4 border-b border-border">
          <Bell className="h-5 w-5 text-primary" />
          <span className="font-semibold text-foreground tracking-tight text-sm">
            shoutrrr-logger
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const visible =
              !user
                ? false
                : item.roles.includes(user.role);
            if (!visible && !isLoading) return null;
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User area */}
        <div className="border-t border-border p-3">
          {isLoading ? (
            <div className="flex items-center gap-2 px-2 py-1.5">
              <Skeleton className="h-7 w-7 rounded-full" />
              <Skeleton className="h-3 w-24" />
            </div>
          ) : user ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary shrink-0">
                    <User className="h-3.5 w-3.5" />
                  </div>
                  <div className="flex-1 text-left min-w-0">
                    <p className="truncate text-xs font-medium text-foreground">
                      {user.username}
                    </p>
                    <p className="truncate text-[11px] text-muted-foreground capitalize">
                      {user.role}
                    </p>
                  </div>
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent side="top" align="start" className="w-48">
                <DropdownMenuLabel className="text-xs text-muted-foreground">
                  {user.email}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild onSelect={(e) => e.preventDefault()}>
                  <PreferencesDialog />
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <a href="/api/auth/logout" className="flex items-center gap-2 text-destructive">
                    <LogOut className="h-3.5 w-3.5" />
                    Sign out
                  </a>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <a
              href="/api/auth/login"
              className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors"
            >
              <LogIn className="h-4 w-4" />
              Sign in
            </a>
          )}
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 inset-x-0 z-50 flex items-center justify-between border-b border-border bg-sidebar px-4 h-12">
        <div className="flex items-center gap-2">
          <Bell className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold text-foreground">shoutrrr-logger</span>
        </div>
        <div className="flex items-center gap-4">
          {user && (
            <Link href="/alerts" className="relative text-muted-foreground hover:text-foreground">
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && <span className="absolute -top-0.5 -right-0.5 flex h-2 w-2 rounded-full bg-destructive" />}
            </Link>
          )}
          {user ? (
            <a href="/api/auth/logout" className="text-xs text-muted-foreground hover:text-foreground">
              Sign out
            </a>
          ) : (
            <a href="/api/auth/login" className="text-xs text-primary">
              Sign in
            </a>
          )}
        </div>
      </div>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0 md:pt-0 pt-12 relative">
        {user && <Topbar />}
        {children}
      </main>
    </div>
  );
}
