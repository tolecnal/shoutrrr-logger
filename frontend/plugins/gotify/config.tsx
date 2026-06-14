"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
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

export function GotifyConfigPanel({
  config,
  onChange,
  onTest,
  saving,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_gotify");
  
  const serverUrl = (config.server_url as string) ?? "";
  const appToken = (config.app_token as string) ?? "";
  const priority = (config.priority as number) ?? 5;
  const messageTemplate = (config.message_template as string) ?? "**{title}**\n\n{message}";
  const useMarkdown = config.use_markdown !== undefined ? (config.use_markdown as boolean) : true;

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
          <Label htmlFor="gotify-server-url">{t('serverUrl')}</Label>
          <Input
            id="gotify-server-url"
            name="gotify-server-url"
            placeholder="https://gotify.example.com"
            value={serverUrl}
            onChange={(e) => onChange({ ...config, server_url: e.target.value })}
            disabled={saving}
          />
          <p className="text-xs text-muted-foreground">{t('serverUrlDesc')}</p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="gotify-app-token">{t('appToken')}</Label>
          <Input
            id="gotify-app-token"
            name="gotify-app-token"
            type="password"
            placeholder={t('appTokenPlaceholder')}
            value={appToken}
            onChange={(e) => onChange({ ...config, app_token: e.target.value })}
            disabled={saving}
          />
          <p className="text-xs text-muted-foreground">{t('appTokenDesc')}</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="gotify-priority">{t('priority')}</Label>
          <Select
            disabled={saving}
            value={priority.toString()}
            onValueChange={(v) => onChange({ ...config, priority: parseInt(v, 10) })}
          >
            <SelectTrigger id="gotify-priority">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 ({t('priorityMin')})</SelectItem>
              <SelectItem value="2">2 ({t('priorityLow')})</SelectItem>
              <SelectItem value="5">5 ({t('priorityDefault')})</SelectItem>
              <SelectItem value="8">8 ({t('priorityHigh')})</SelectItem>
              <SelectItem value="10">10 ({t('priorityMax')})</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{t('priorityDesc')}</p>
        </div>

        <div className="space-y-1.5 flex flex-col justify-center">
          <Label htmlFor="gotify-use-markdown">{t('useMarkdown')}</Label>
          <div className="flex items-center gap-2 mt-1">
            <Switch
              id="gotify-use-markdown"
              checked={useMarkdown}
              onCheckedChange={(checked) => onChange({ ...config, use_markdown: checked })}
              disabled={saving}
            />
            <span className="text-sm">{useMarkdown ? t('enabled') : t('disabled')}</span>
          </div>
          <p className="text-xs text-muted-foreground mt-1">{t('useMarkdownDesc')}</p>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="gotify-message-template">{t('messageTemplate')}</Label>
        <Textarea
          id="gotify-message-template"
          name="gotify-message-template"
          placeholder="**{title}**\n\n{message}"
          rows={3}
          value={messageTemplate}
          onChange={(e) => onChange({ ...config, message_template: e.target.value })}
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">{t('messageTemplateDesc')}</p>
      </div>

      <Separator />

      <div className="flex items-center gap-4 py-3">
        <Button
          size="sm"
          onClick={handleTest}
          disabled={testState === "loading" || saving || !serverUrl || !appToken}
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
