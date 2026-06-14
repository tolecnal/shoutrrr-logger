"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Send, CheckCircle2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PluginConfigProps } from "../types";
import { useState } from "react";
import { useTranslations } from "next-intl";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import jsonLang from "react-syntax-highlighter/dist/esm/languages/hljs/json";
import { vs2015 } from "react-syntax-highlighter/dist/esm/styles/hljs";

SyntaxHighlighter.registerLanguage("json", jsonLang);

export function WebhookConfigPanel({
  config,
  onChange,
  onTest,
  saving,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_webhook");
  const url = (config.url as string) ?? "";
  const method = (config.method as string) ?? "POST";
  const headers = (config.headers as string) ?? '{"Content-Type": "application/json"}';
  const payloadTemplate = (config.payload_template as string) ?? '{"title": "{title}", "message": "{message}"}';
  const tlsVerification = config.tls_verification !== undefined ? (config.tls_verification as boolean) : true;

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

  // Generate a preview payload
  const previewData: Record<string, string> = {
    title: "Example Alert Title",
    message: "This is what an example notification message looks like.",
    severity: "warning",
    "custom_fields.app_name": "backend-api",
  };

  let renderedPayload = payloadTemplate;
  for (const [key, value] of Object.entries(previewData)) {
    // JSON.stringify handles all JSON escape sequences (backslashes, quotes,
    // newlines, control characters, ...); slice off the surrounding quotes
    // since the value is substituted inside an existing template string.
    const escapedValue = JSON.stringify(String(value)).slice(1, -1);
    renderedPayload = renderedPayload.replaceAll(`{${key}}`, escapedValue);
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-4">
        <div className="sm:col-span-3 space-y-1.5">
          <Label htmlFor="webhook-url">{t('webhookUrl')}</Label>
          <Input
            id="webhook-url"
            name="webhook-url"
            placeholder="https://example.com/webhook"
            value={url}
            onChange={(e) => onChange({ ...config, url: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            {t('webhookUrlDesc')}
          </p>
        </div>
        <div className="sm:col-span-1 space-y-1.5">
          <Label>{t('method')}</Label>
          <Select value={method} onValueChange={(value) => onChange({ ...config, method: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="POST">POST</SelectItem>
              <SelectItem value="PUT">PUT</SelectItem>
              <SelectItem value="PATCH">PATCH</SelectItem>
              <SelectItem value="GET">GET</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-row items-center justify-between rounded-lg border p-3 shadow-sm bg-muted/20">
        <div className="space-y-0.5">
          <Label>{t('tlsVerification')}</Label>
          <p className="text-xs text-muted-foreground">
            {t('tlsVerificationDesc')}
          </p>
        </div>
        <Switch
          checked={tlsVerification}
          onCheckedChange={(checked) => onChange({ ...config, tls_verification: checked })}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="webhook-headers">{t('headersJson')}</Label>
        <Textarea
          id="webhook-headers"
          name="webhook-headers"
          rows={3}
          value={headers}
          onChange={(e) => onChange({ ...config, headers: e.target.value })}
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          {t('headersJsonDesc')}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="webhook-payload-template">{t('payloadTemplate')}</Label>
          <Textarea
            id="webhook-payload-template"
            name="webhook-payload-template"
            rows={10}
            value={payloadTemplate}
            onChange={(e) => onChange({ ...config, payload_template: e.target.value })}
            className="font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">
            {t('payloadTemplateDesc')}
          </p>
        </div>

        <div className="space-y-1.5">
          <Label>{t('payloadPreview')}</Label>
          <div className="h-[212px] overflow-auto rounded-md border bg-[#1e1e1e] p-0 relative">
            <SyntaxHighlighter
              language="json"
              style={vs2015}
              customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '11px', lineHeight: '1.5' }}
              wrapLines={true}
              wrapLongLines={true}
            >
              {renderedPayload}
            </SyntaxHighlighter>
          </div>
          <p className="text-xs text-muted-foreground">
            {t('payloadPreviewDesc')}
          </p>
        </div>
      </div>

      <Separator />

      <div className="flex items-center gap-4 py-3">
        <Button
          size="sm"
          onClick={handleTest}
          disabled={testState === "loading" || saving || !url}
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
