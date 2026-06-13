"use client";

import useSWR from "swr";
import { fetchVersion } from "@/lib/api";
import { FRONTEND_VERSION, API_VERSION_PREFIX } from "@/lib/version";
import { usePreferences } from "@/lib/use-preferences";
import { GitCommitHorizontal, Clock, Tag, RefreshCw, AlertTriangle, Server, Monitor } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { useTranslations } from "next-intl";

function Row({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start gap-4 py-3 border-b border-border last:border-0">
      <span className="text-sm text-muted-foreground w-32 shrink-0">{label}</span>
      <span className={cn("text-sm text-foreground break-all", mono && "font-mono")}>{value}</span>
    </div>
  );
}

function Section({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{title}</p>
      </div>
      <div className="rounded-lg border border-border bg-card px-4">{children}</div>
    </div>
  );
}

export function VersionPage() {
  const t = useTranslations("About");
  const { data, error, isLoading, mutate } = useSWR("/api/version", fetchVersion, {
    revalidateOnFocus: false,
  });
  const { formatTimestamp } = usePreferences();

  const buildDate =
    data?.build_time && data.build_time !== "unknown"
      ? formatTimestamp(data.build_time)
      : (data?.build_time ?? null);

  // Detect a version skew between what this frontend build expects and
  // what the backend is actually serving.
  const apiMismatch = data && data.api_version !== API_VERSION_PREFIX;

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-6 py-4 border-b border-border bg-card/40 flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-foreground">{t('title')}</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {t('description')}
          </p>
        </div>
        <button
          onClick={() => mutate()}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label={t('refreshVersion')}
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-lg">
          {/* App identity */}
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-foreground">shoutrrr-logger</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {t('appDescription')}
            </p>
          </div>

          {/* Version mismatch warning */}
          {apiMismatch && (
            <div className="flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 mb-6 text-sm text-destructive">
              <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>
                {t('apiMismatchPrefix')}<span className="font-mono font-semibold">{API_VERSION_PREFIX}</span>{t('apiMismatchMid')}
                <span className="font-mono font-semibold">{data?.api_version}</span>{t('apiMismatchSuffix')}
              </span>
            </div>
          )}

          {/* Frontend section */}
          <Section icon={Monitor} title={t('frontend')}>
            <Row label={t('version')} value={
              <span className="inline-flex items-center gap-1.5">
                <Tag className="h-3.5 w-3.5 text-muted-foreground" />
                {FRONTEND_VERSION}
              </span>
            } />
            <Row label={t('apiTarget')} value={
              <span className="font-mono">{API_VERSION_PREFIX}</span>
            } />
          </Section>

          {/* Backend section */}
          <Section icon={Server} title={t('backend')}>
            {isLoading ? (
              <div className="space-y-3 py-3">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-4 w-64" />
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-4 w-56" />
              </div>
            ) : error ? (
              <p className="py-3 text-sm text-destructive">{t('failedToLoad')}</p>
            ) : data ? (
              <>
                <Row label={t('version')} value={
                  <span className="inline-flex items-center gap-1.5">
                    <Tag className="h-3.5 w-3.5 text-muted-foreground" />
                    {data.version}
                  </span>
                } />
                <Row label={t('apiVersion')} value={
                  <span className={cn("font-mono", apiMismatch && "text-destructive font-semibold")}>
                    {data.api_version}
                  </span>
                } />
                <Row label={t('gitCommit')} value={
                  <span className="inline-flex items-center gap-1.5">
                    <GitCommitHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
                    {data.git_hash}
                  </span>
                } mono />
                <Row label={t('builtAt')} value={
                  <span className="inline-flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    {buildDate ?? t('unknown')}
                  </span>
                } />
              </>
            ) : null}
          </Section>
        </div>
      </div>
    </div>
  );
}
