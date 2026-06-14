"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Send, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PluginConfigProps } from "../types";
import { useState } from "react";
import { useTranslations } from "next-intl";

export function PagerDutyConfigPanel({
  config,
  onChange,
  onTest,
  saving,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_pagerduty");
  
  const integrationKey = (config.integration_key as string) ?? "";
  const source = (config.source as string) ?? "Shoutrrr Logger";
  const severity = (config.severity as string) ?? "info";

  const [testState, setTestState] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [testMsg, setTestMsg] = useState("");

  const handleTest = async () => {
    setTestState("loading");
    setTestMsg("");
    try {
      await onTest();
      setTestState("ok");
    } catch (e: any) {
      setTestState("err");
      setTestMsg(e.message);
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="pd-integration-key">{t('integrationKey')}</Label>
          <Input
            id="pd-integration-key"
            name="pd-integration-key"
            type="password"
            value={integrationKey}
            onChange={(e) => onChange({ ...config, integration_key: e.target.value })}
            disabled={saving}
          />
          <p className="text-xs text-muted-foreground">{t('integrationKeyDesc')}</p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="pd-source">{t('source')}</Label>
          <Input
            id="pd-source"
            name="pd-source"
            placeholder="Shoutrrr Logger"
            value={source}
            onChange={(e) => onChange({ ...config, source: e.target.value })}
            disabled={saving}
          />
          <p className="text-xs text-muted-foreground">{t('sourceDesc')}</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="pd-severity">{t('severity')}</Label>
          <Select
            disabled={saving}
            value={severity}
            onValueChange={(v) => onChange({ ...config, severity: v })}
          >
            <SelectTrigger id="pd-severity">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="critical">{t('severityCritical')}</SelectItem>
              <SelectItem value="error">{t('severityError')}</SelectItem>
              <SelectItem value="warning">{t('severityWarning')}</SelectItem>
              <SelectItem value="info">{t('severityInfo')}</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{t('severityDesc')}</p>
        </div>
      </div>

      <Separator />

      <div className="flex items-center gap-4 py-3">
        <Button
          size="sm"
          onClick={handleTest}
          disabled={testState === "loading" || saving || !integrationKey}
          className="gap-1.5"
        >
          <Send className="h-3.5 w-3.5" />
          {testState === "loading" ? t('sending') : t('sendTestNotification')}
        </Button>
        {testState !== "idle" && (
          <span
            className={cn(
              "flex items-center gap-1 text-xs",
              testState === "ok" ? "text-green-600" : "text-destructive"
            )}
          >
            {testState === "ok" ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <XCircle className="h-3 w-3" />
            )}
            {testState === "ok" ? t("testSuccess") : `${t("testFailed")}${testMsg}`}
          </span>
        )}
      </div>
    </div>
  );
}
