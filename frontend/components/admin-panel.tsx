"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { KeyRound, Puzzle, ScrollText, Settings2, Users } from "lucide-react";
import { UsersTab } from "@/components/admin-users-tab";
import { TokensTab } from "@/components/admin-tokens-tab";
import { PluginsTab } from "@/components/admin-plugins-tab";
import { SettingsTab } from "@/components/admin-settings-tab";
import { AuditLogTab } from "@/components/admin-audit-log-tab";

export function AdminPanel() {
  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Page header */}
      <div className="px-6 py-4 border-b border-border bg-card/40">
        <h1 className="text-base font-semibold text-foreground">Admin</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Manage users, access tokens, plugins, and application settings.
        </p>
      </div>

      <div className="flex-1 overflow-auto px-6 py-4">
        <Tabs defaultValue="users" className="flex flex-col gap-4">
          <TabsList className="w-fit bg-muted">
            <TabsTrigger value="users" className="flex items-center gap-1.5 text-xs">
              <Users className="h-3.5 w-3.5" />
              Users
            </TabsTrigger>
            <TabsTrigger value="tokens" className="flex items-center gap-1.5 text-xs">
              <KeyRound className="h-3.5 w-3.5" />
              Access Tokens
            </TabsTrigger>
            <TabsTrigger value="plugins" className="flex items-center gap-1.5 text-xs">
              <Puzzle className="h-3.5 w-3.5" />
              Plugins
            </TabsTrigger>
            <TabsTrigger value="settings" className="flex items-center gap-1.5 text-xs">
              <Settings2 className="h-3.5 w-3.5" />
              Settings
            </TabsTrigger>
            <TabsTrigger value="audit-log" className="flex items-center gap-1.5 text-xs">
              <ScrollText className="h-3.5 w-3.5" />
              Audit Log
            </TabsTrigger>
          </TabsList>

          <TabsContent value="users" className="mt-0">
            <UsersTab />
          </TabsContent>

          <TabsContent value="tokens" className="mt-0">
            <TokensTab />
          </TabsContent>

          <TabsContent value="plugins" className="mt-0">
            <PluginsTab />
          </TabsContent>

          <TabsContent value="settings" className="mt-0">
            <SettingsTab />
          </TabsContent>

          <TabsContent value="audit-log" className="mt-0">
            <AuditLogTab />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
