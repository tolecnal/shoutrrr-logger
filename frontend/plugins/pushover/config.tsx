"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
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

export function PushoverConfigPanel({
  config,
  onChange,
  onTest,
  saving,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_pushover");
  
  const userKey = (config.user_key as string) ?? "";
  const apiToken = (config.api_token as string) ?? "";
  const titleTemplate = (config.title_template as string) ?? "{title}";
  const messageTemplate = (config.message_template as string) ?? "{message}";
  const priority = (config.priority as string) ?? "0";
  const sound = (config.sound as string) ?? "pushover";
  const device = (config.device as string) ?? "";

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
          <Label htmlFor="pushover-user-key">{t('userKey')}</Label>
          <Input
            id="pushover-user-key"
            name="pushover-user-key"
            type="password"
            placeholder="u..."
            value={userKey}
            onChange={(e) => onChange({ ...config, user_key: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t('userKeyDesc')}</p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="pushover-api-token">{t('apiToken')}</Label>
          <Input
            id="pushover-api-token"
            name="pushover-api-token"
            type="password"
            placeholder="a..."
            value={apiToken}
            onChange={(e) => onChange({ ...config, api_token: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t('apiTokenDesc')}</p>
        </div>
      </div>
      
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="pushover-priority">{t('priority')}</Label>
          <Select
            value={priority}
            onValueChange={(val) => onChange({ ...config, priority: val })}
          >
            <SelectTrigger id="pushover-priority">
              <SelectValue placeholder="Select priority" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="-2">{t('priorityLowest')} (-2)</SelectItem>
              <SelectItem value="-1">{t('priorityLow')} (-1)</SelectItem>
              <SelectItem value="0">{t('priorityNormal')} (0)</SelectItem>
              <SelectItem value="1">{t('priorityHigh')} (1)</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{t('priorityDesc')}</p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="pushover-sound">{t('sound')}</Label>
          <Input
            id="pushover-sound"
            name="pushover-sound"
            placeholder="pushover"
            value={sound}
            onChange={(e) => onChange({ ...config, sound: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">{t('soundDesc')}</p>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="pushover-device">{t('device')}</Label>
        <Input
          id="pushover-device"
          name="pushover-device"
          placeholder="iphone,ipad"
          value={device}
          onChange={(e) => onChange({ ...config, device: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">{t('deviceDesc')}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="pushover-title-template">{t('titleTemplate')}</Label>
          <Input
            id="pushover-title-template"
            name="pushover-title-template"
            value={titleTemplate}
            onChange={(e) => onChange({ ...config, title_template: e.target.value })}
            className="font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">{t('titleTemplateDesc')}</p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pushover-message-template">{t('messageTemplate')}</Label>
          <Textarea
            id="pushover-message-template"
            name="pushover-message-template"
            rows={3}
            value={messageTemplate}
            onChange={(e) => onChange({ ...config, message_template: e.target.value })}
            className="font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">{t('messageTemplateDesc')}</p>
        </div>
      </div>

      <div className="pt-2 border-t flex items-center justify-between">
        <div className="text-sm">
          {testError && <span className="text-destructive">{t('testFailed')}{testError}</span>}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleTest}
          disabled={testing || saving || !userKey || !apiToken}
          className="gap-2"
        >
          <Send className="h-4 w-4" />
          {testing ? t('sending') : t('sendTestNotification')}
        </Button>
      </div>
    </div>
  );
}
