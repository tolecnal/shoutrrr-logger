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

export function TeamsConfigPanel({
  config,
  onChange,
  onTest,
  saving,
  availableCustomFields,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_teams");
  const url = (config.webhook_url as string) ?? "";
  const messageTemplate = (config.message_template as string) ?? "**{title}**\n\n{message}";
  const includedFields = (config.included_fields as string[]) ?? ["severity", "source_ip", "received_at"];
  const themeColor = (config.theme_color as string) ?? "0076D7";

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
        <Label htmlFor="teams-webhook-url">{t('webhookUrl')}</Label>
        <Input
          id="teams-webhook-url"
          name="teams-webhook-url"
          placeholder="https://YOUR_TENANT.webhook.office.com/..."
          value={url}
          onChange={(e) => onChange({ ...config, webhook_url: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          {t('webhookUrlDesc')}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="teams-message-template">{t('messageTemplate')}</Label>
          <Textarea
            id="teams-message-template"
            name="teams-message-template"
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
            <Label htmlFor="teams-theme-color">{t('themeColor')}</Label>
            <div className="flex gap-2">
              <div 
                className="w-10 h-10 rounded border shrink-0" 
                style={{ backgroundColor: `#${themeColor}` }}
              />
              <Input
                id="teams-theme-color"
                name="teams-theme-color"
                value={themeColor}
                onChange={(e) => {
                  // strip # if user pastes it
                  const val = e.target.value.replace("#", "");
                  onChange({ ...config, theme_color: val });
                }}
                placeholder="0076D7"
              />
            </div>
            <p className="text-xs text-muted-foreground">
              {t('themeColorDesc')}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="teams-new-field">{t('includedFields')}</Label>
            <Input
              id="teams-new-field"
              placeholder={t('includedFieldsPlaceholder')}
              value={newField}
              onChange={(e) => setNewField(e.target.value)}
              onKeyDown={addField}
              list="teams-available-fields"
            />
            <datalist id="teams-available-fields">
              {availableCustomFields.map(f => <option key={f} value={f} />)}
            </datalist>
            {includedFields.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-2">
                {includedFields.map((f) => (
                  <Badge key={f} variant="secondary" className="text-xs">
                    {f}
                    <button
                      type="button"
                      onClick={() => removeField(f)}
                      className="ml-1 hover:text-destructive focus:outline-none"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              {t('includedFieldsDesc')}
            </p>
          </div>
        </div>
      </div>

      <Separator />

      <div className="flex items-center gap-4 py-3">
        <Button
          type="button"
          variant="default"
          size="sm"
          disabled={!url || saving || testState === "loading"}
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
