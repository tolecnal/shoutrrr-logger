"use client";

import { useState } from "react";
import useSWR from "swr";
import { Puzzle } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchUserPlugins,
  createUserPluginProfile,
  updateUserPluginProfile,
  deleteUserPluginProfile,
  testUserPluginProfile,
  fetchCustomFieldKeys,
} from "@/lib/api";
import type { UserPluginOut } from "@/lib/types";
import {
  PluginCardHeader,
  PluginProfileTabs,
  type ProfileApi,
} from "@/components/plugin-profile-tabs";
import { ExternalDeliveryWarning } from "@/components/external-delivery-warning";
import { useTranslations } from "next-intl";

const userProfileApi: ProfileApi = {
  create: createUserPluginProfile,
  update: updateUserPluginProfile,
  remove: deleteUserPluginProfile,
  test: testUserPluginProfile,
};

function UserPluginCard({
  userPlugin,
  availableCustomFields,
  onSaved,
}: {
  userPlugin: UserPluginOut;
  availableCustomFields: string[];
  onSaved: () => void;
}) {
  const tPlugin = useTranslations();
  const [expanded, setExpanded] = useState(false);
  const enabledCount = userPlugin.profiles.filter((p) => p.enabled).length;

  return (
    <div className="rounded-lg border border-border bg-card">
      <PluginCardHeader
        pluginId={userPlugin.plugin_id}
        name={tPlugin.has(`Plugin_${userPlugin.plugin_id}.name`) ? tPlugin(`Plugin_${userPlugin.plugin_id}.name`) : userPlugin.name}
        description={tPlugin.has(`Plugin_${userPlugin.plugin_id}.description`) ? tPlugin(`Plugin_${userPlugin.plugin_id}.description`) : userPlugin.description}
        enabledCount={enabledCount}
        expanded={expanded}
        onToggle={() => setExpanded((v) => !v)}
      />
      {expanded && (
        <>
          <Separator />
          <div className="px-4 py-4">
            <PluginProfileTabs
              pluginId={userPlugin.plugin_id}
              pluginName={tPlugin.has(`Plugin_${userPlugin.plugin_id}.name`) ? tPlugin(`Plugin_${userPlugin.plugin_id}.name`) : userPlugin.name}
              profiles={userPlugin.profiles}
              maxProfiles={userPlugin.max_profiles}
              availableCustomFields={availableCustomFields}
              api={userProfileApi}
              onSaved={onSaved}
            />
          </div>
        </>
      )}
    </div>
  );
}

export function UserPluginsTab({
  externalDeliveryDisabled = false,
}: {
  externalDeliveryDisabled?: boolean;
}) {
  const t = useTranslations("UserPlugins");
  const { data: userPlugins, isLoading, mutate } = useSWR<UserPluginOut[]>(
    "/api/v1/user-plugins",
    fetchUserPlugins,
    { revalidateOnFocus: false }
  );
  const { data: customFieldKeys = [] } = useSWR<string[]>(
    "/api/v1/admin/plugins/custom-field-keys",
    fetchCustomFieldKeys,
    { revalidateOnFocus: false }
  );

  if (isLoading) {
    return (
      <div className="space-y-3 mt-4">
        <Skeleton className="h-14 w-full rounded-lg" />
        <Skeleton className="h-14 w-full rounded-lg" />
      </div>
    );
  }

  if (!userPlugins?.length) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
        <Puzzle className="h-8 w-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">{t('noPlugins')}</p>
      </div>
    );
  }

  return (
    <div className="flex-1 min-h-0 overflow-y-auto mt-4 pr-1 space-y-3">
      {externalDeliveryDisabled && (
        <ExternalDeliveryWarning message={t('externalDisabled')} />
      )}
      {userPlugins.map((plugin) => (
        <UserPluginCard
          key={plugin.plugin_id}
          userPlugin={plugin}
          availableCustomFields={customFieldKeys}
          onSaved={() => mutate()}
        />
      ))}
    </div>
  );
}
