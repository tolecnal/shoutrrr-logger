"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { X, Send, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PluginConfigProps } from "../types";
import { useState } from "react";
import { useTranslations } from "next-intl";

export function SlackConfigPanel({
  config,
  onChange,
  onTest,
  saving,
  availableCustomFields,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_slack");
  const url = (config.webhook_url as string) ?? "";
  const messageTemplate = (config.message_template as string) ?? "*{title}*\n{message}";
  const includedFields = (config.included_fields as string[]) ?? ["received_at", "source_ip", "severity"];
  const emoji = (config.emoji as string) ?? ":rotating_light:";

  const [testState, setTestState] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [testMsg, setTestMsg] = useState("");

  const [newField, setNewField] = useState("");

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

  const addField = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && newField.trim()) {
      e.preventDefault();
      if (!includedFields.includes(newField.trim())) {
        onChange({ ...config, included_fields: [...includedFields, newField.trim()] });
      }
      setNewField("");
    }
  };

  const removeField = (field: string) => {
    onChange({ ...config, included_fields: includedFields.filter((f) => f !== field) });
  };

  return (
    <div className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="slack-webhook-url">{t('webhookUrl')}</Label>
        <Input
          id="slack-webhook-url"
          name="slack-webhook-url"
          placeholder="https://hooks.slack.com/services/..."
          value={url}
          onChange={(e) => onChange({ ...config, webhook_url: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          {t('webhookUrlDesc')}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="slack-message-template">{t('messageTemplate')}</Label>
          <Textarea
            id="slack-message-template"
            name="slack-message-template"
            rows={4}
            value={messageTemplate}
            onChange={(e) => onChange({ ...config, message_template: e.target.value })}
            className="font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">
            {t('messageTemplateDesc')}
          </p>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="slack-emoji">{t('emojiIcon')}</Label>
            <Input
              id="slack-emoji"
              name="slack-emoji"
              value={emoji}
              onChange={(e) => onChange({ ...config, emoji: e.target.value })}
              placeholder=":rotating_light:"
            />
            <p className="text-xs text-muted-foreground">
              {t('emojiIconDesc')}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label>{t('includedFields')}</Label>
            <div className="flex flex-wrap gap-1 mb-1.5 min-h-[28px] p-2 border rounded-md bg-muted/20">
              {includedFields.length === 0 && (
                <span className="text-xs text-muted-foreground italic px-1">{t('noAdditionalFields')}</span>
              )}
              {includedFields.map((field) => (
                <Badge key={field} variant="secondary" className="pr-1 text-xs font-normal">
                  {field}
                  <button
                    className="ml-1 text-muted-foreground hover:text-foreground"
                    onClick={() => removeField(field)}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
            <Input
              id="slack-included-field"
              name="slack-included-field"
              placeholder={t('addFieldPlaceholder')}
              value={newField}
              onChange={(e) => setNewField(e.target.value)}
              onKeyDown={addField}
              list="slack-field-suggestions"
              className="h-8 text-xs"
            />
            <datalist id="slack-field-suggestions">
              {["severity", "tags", "source_ip", "received_at", "fingerprint"].map((f) => (
                <option key={f} value={f} />
              ))}
              {availableCustomFields.map((cf) => (
                <option key={`custom_fields.${cf}`} value={`custom_fields.${cf}`} />
              ))}
            </datalist>
          </div>
        </div>
      </div>

      <Separator />

      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant="secondary"
          onClick={handleTest}
          disabled={testState === "loading" || saving || !url}
          className="h-7 text-xs gap-1.5"
        >
          <Send className="h-3 w-3" />
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

      {/* Preview box */}
      <div className="mt-6 border rounded-lg overflow-hidden">
        <div className="bg-muted px-4 py-2 border-b">
          <p className="text-xs font-medium text-muted-foreground">{t('slackMessagePreview')}</p>
        </div>
        <div className="p-4 bg-background flex gap-3">
          <div className="w-9 h-9 rounded bg-muted flex items-center justify-center shrink-0 text-xl" title={t('emojiTitle')}>
            🚨
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 mb-1">
              <span className="font-bold text-[15px]">shoutrrr-logger</span>
              <span className="text-xs text-muted-foreground">8:00 AM</span>
            </div>
            <div className="text-[15px] whitespace-pre-wrap">
              <strong>{t('previewNotification')}</strong>
              <br />
              {t('previewBody')}
            </div>
            {includedFields.length > 0 && (
              <div className="mt-2 border-l-4 border-[#e3e4e6] pl-3 py-1 flex gap-x-8 gap-y-2 flex-wrap">
                {includedFields.map((field) => (
                  <div key={field} className="text-sm">
                    <div className="font-bold text-muted-foreground mb-0.5">{field}</div>
                    <div>{t('value')}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
