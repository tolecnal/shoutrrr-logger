"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Send } from "lucide-react";
import type { PluginConfigProps } from "../types";
import { useState } from "react";
import { useTranslations } from "next-intl";

export function NtfyConfigPanel({
  config,
  onChange,
  onTest,
  saving,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_ntfy");
  
  const serverUrl = (config.server_url as string) ?? "https://ntfy.sh";
  const topic = (config.topic as string) ?? "";
  const priority = (config.priority as string) ?? "default";
  const tags = (config.tags as string) ?? "";
  const messageTemplate = (config.message_template as string) ?? "{title}\n{message}";
  const accessToken = (config.access_token as string) ?? "";

  const [testError, setTestError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  const handleTest = async () => {
    setTesting(true);
    setTestError(null);
    try {
      await onTest();
    } catch (e: any) {
      setTestError(e.message);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="ntfy-server-url">{t('serverUrl')}</Label>
          <Input
            id="ntfy-server-url"
            name="ntfy-server-url"
            placeholder="https://ntfy.sh"
            value={serverUrl}
            onChange={(e) => onChange({ ...config, server_url: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t('serverUrlDesc')}</p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="ntfy-topic">{t('topic')}</Label>
          <Input
            id="ntfy-topic"
            name="ntfy-topic"
            placeholder="my_secret_topic"
            value={topic}
            onChange={(e) => onChange({ ...config, topic: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t('topicDesc')}</p>
        </div>
      </div>
      
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="ntfy-priority">{t('priority')}</Label>
          <Select
            value={priority}
            onValueChange={(val) => onChange({ ...config, priority: val })}
          >
            <SelectTrigger id="ntfy-priority">
              <SelectValue placeholder="Select priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="min">{t('priorityMin')} (1)</SelectItem>
              <SelectItem value="low">{t('priorityLow')} (2)</SelectItem>
              <SelectItem value="default">{t('priorityDefault')} (3)</SelectItem>
              <SelectItem value="high">{t('priorityHigh')} (4)</SelectItem>
              <SelectItem value="max">{t('priorityMax')} (5)</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{t('priorityDesc')}</p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="ntfy-tags">{t('tags')}</Label>
          <Input
            id="ntfy-tags"
            name="ntfy-tags"
            placeholder="warning,skull"
            value={tags}
            onChange={(e) => onChange({ ...config, tags: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t('tagsDesc')}</p>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ntfy-access-token">{t('accessToken')}</Label>
        <Input
          id="ntfy-access-token"
          name="ntfy-access-token"
          type="password"
          placeholder="tk_..."
          value={accessToken}
          onChange={(e) => onChange({ ...config, access_token: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">{t('accessTokenDesc')}</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="ntfy-message-template">{t('messageTemplate')}</Label>
        <Textarea
          id="ntfy-message-template"
          name="ntfy-message-template"
          rows={3}
          value={messageTemplate}
          onChange={(e) => onChange({ ...config, message_template: e.target.value })}
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">{t('messageTemplateDesc')}</p>
      </div>

      <Separator />

      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant="secondary"
          onClick={handleTest}
          disabled={testing || saving || !serverUrl || !topic}
          className="h-7 text-xs gap-1.5"
        >
          <Send className="h-3 w-3" />
          {testing ? t('sending') : t('sendTestNotification')}
        </Button>
        {testError && <span className="text-xs text-destructive">{t('testFailed')} {testError}</span>}
      </div>
    </div>
  );
}
