"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Send, CheckCircle2, XCircle } from "lucide-react";
import type { PluginConfigProps } from "../types";
import { useState } from "react";
import { useTranslations } from "next-intl";

export function MatrixConfigPanel({
  config,
  onChange,
  onTest,
  saving,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_matrix");
  const url = (config.homeserver_url as string) ?? "https://matrix.org";
  const accessToken = (config.access_token as string) ?? "";
  const roomId = (config.room_id as string) ?? "";
  const messageTemplate = (config.message_template as string) ?? "**{title}**\n\n{message}";

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
          <Label htmlFor="matrix-url">{t('homeserverUrl')}</Label>
          <Input
            id="matrix-url"
            name="matrix-url"
            placeholder="https://matrix.org"
            value={url}
            onChange={(e) => onChange({ ...config, homeserver_url: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            {t('homeserverUrlDesc')}
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="matrix-room-id">{t('roomId')}</Label>
          <Input
            id="matrix-room-id"
            name="matrix-room-id"
            placeholder="!abcdefg:matrix.org"
            value={roomId}
            onChange={(e) => onChange({ ...config, room_id: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            {t('roomIdDesc')}
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="matrix-access-token">{t('accessToken')}</Label>
        <Input
          id="matrix-access-token"
          name="matrix-access-token"
          type="password"
          placeholder="syt_..."
          value={accessToken}
          onChange={(e) => onChange({ ...config, access_token: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          {t('accessTokenDesc')}
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="matrix-message-template">{t('messageTemplate')}</Label>
        <Textarea
          id="matrix-message-template"
          name="matrix-message-template"
          rows={4}
          value={messageTemplate}
          onChange={(e) => onChange({ ...config, message_template: e.target.value })}
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          {t('messageTemplateDesc')}
        </p>
      </div>

      <Separator />

      <div className="flex items-center gap-4 py-3">
        <Button
          type="button"
          variant="default"
          size="sm"
          disabled={!url || !accessToken || !roomId || saving || testState === "loading"}
          onClick={handleTest}
        >
          {testState === "loading" ? (
            <span className="flex items-center gap-2">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
              {t('testing')}
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <Send className="h-4 w-4" />
              {t('testButton')}
            </span>
          )}
        </Button>

        {testState === "ok" && (
          <span className="flex items-center gap-1.5 text-sm font-medium text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="h-4 w-4" />
            {t('testSuccess')}
          </span>
        )}

        {testState === "err" && (
          <span className="flex items-center gap-1.5 text-sm font-medium text-destructive">
            <XCircle className="h-4 w-4 shrink-0" />
            <span className="line-clamp-1">{t('testFailed')}: {testMsg}</span>
          </span>
        )}
      </div>
    </div>
  );
}
