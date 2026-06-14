"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";
import { Spinner } from "@/components/ui/spinner";
import { StatsPanel } from "@/components/stats-panel";
import { PluginStatsPanel } from "@/components/plugin-stats-panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function StatsPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) router.replace("/api/auth/login");
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user) return null;

  if (user.role !== "admin") {
    // Regular users only see their own plugin usage
    return (
      <div className="flex-1 space-y-4 p-4 md:p-8 pt-6">
        <PluginStatsPanel />
      </div>
    );
  }

  // Admins see both
  return (
    <div className="flex-1 space-y-4 p-4 md:p-8 pt-6">
      <Tabs defaultValue="notifications" className="space-y-4">
        <TabsList>
          <TabsTrigger value="notifications">Notification Stats</TabsTrigger>
          <TabsTrigger value="plugins">Plugin Stats</TabsTrigger>
        </TabsList>
        <TabsContent value="notifications" className="space-y-4">
          <StatsPanel />
        </TabsContent>
        <TabsContent value="plugins" className="space-y-4">
          <PluginStatsPanel />
        </TabsContent>
      </Tabs>
    </div>
  );
}
