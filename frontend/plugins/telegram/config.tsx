"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Send, AlertCircle, CheckCircle2 } from "lucide-react";
import type { PluginConfigProps } from "@/plugins/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import jsonLang from "react-syntax-highlighter/dist/esm/languages/hljs/json";
import { vs2015 } from "react-syntax-highlighter/dist/esm/styles/hljs";

SyntaxHighlighter.registerLanguage("json", jsonLang);

type TelegramConfig = {
  bot_token: string;
  chat_id: string;
  message_template: string;
  included_fields: string[];
};

function toTelegramConfig(raw: Record<string, unknown>): TelegramConfig {
  return {
    bot_token: String(raw.bot_token ?? ""),
    chat_id: String(raw.chat_id ?? ""),
    message_template: String(raw.message_template ?? "<b>{title}</b>\n\n{message}"),
    included_fields: Array.isArray(raw.included_fields)
      ? raw.included_fields.map(String)
      : ["severity", "source_ip"],
  };
}

export function TelegramConfigPanel({
  config: rawConfig,
  onChange,
  onTest,
  saving,
  availableCustomFields,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_telegram");
  const config = toTelegramConfig(rawConfig);
  const [testState, setTestState] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [testMsg, setTestMsg] = useState("");

  function update<K extends keyof TelegramConfig>(key: K, value: TelegramConfig[K]) {
    onChange({ ...rawConfig, [key]: value });
  }

  async function handleTest() {
    setTestState("loading");
    setTestMsg("");
    try {
      await onTest();
      setTestState("ok");
      setTestMsg("");
    } catch (e: unknown) {
      setTestState("err");
      setTestMsg(e instanceof Error ? `${t("testFailed")}${e.message}` : "Error");
    }
  }

  // Build a preview of the Telegram payload
  const sampleCustomFields: Record<string, string> = {};
  for (const k of availableCustomFields) sampleCustomFields[k] = `<${k}>`;

  const sample: Record<string, unknown> = {
    id: "a1b2c3d4",
    title: "Deploy succeeded",
    message: "Production v0.2.0 deployed successfully.",
    received_at: 1749412800.0,
    source_ip: "10.0.0.1",
    severity: "info",
    custom_fields: sampleCustomFields,
  };

  let messageText = config.message_template;
  for (const [k, v] of Object.entries(sample)) {
    messageText = messageText.replace(`{${k}}`, String(v));
  }
  for (const [k, v] of Object.entries(sampleCustomFields)) {
    messageText = messageText.replace(`{custom_fields.${k}}`, String(v));
  }

  if (config.included_fields.length > 0) {
    messageText += "\n\n<b>Details:</b>\n<pre>";
    for (const field of config.included_fields) {
      let val: any = undefined;
      if (field.startsWith("custom_fields.")) {
        const k = field.replace("custom_fields.", "");
        val = sampleCustomFields[k] ?? `<${k}>`;
      } else {
        val = sample[field];
      }
      if (val !== undefined) {
        messageText += `${field}: ${val}\n`;
      }
    }
    messageText += "</pre>";
  }

  const previewPayload = {
    chat_id: config.chat_id || "<chat_id>",
    text: messageText,
    parse_mode: "HTML",
    disable_web_page_preview: true,
  };

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        <div className="grid gap-2">
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="telegram-bot-token">
              {t("botToken")}
            </Label>
            <Input
              id="telegram-bot-token"
              name="telegram-bot-token"
              type="password"
              value={config.bot_token}
              onChange={(e) => update("bot_token", e.target.value)}
              placeholder="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
              className="h-7 text-xs font-mono"
            />
            <p className="text-[11px] text-muted-foreground">{t("botTokenDesc")}</p>
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="telegram-chat-id">
              {t("chatId")}
            </Label>
            <Input
              id="telegram-chat-id"
              name="telegram-chat-id"
              value={config.chat_id}
              onChange={(e) => update("chat_id", e.target.value)}
              placeholder="-1001234567890 or @channelname"
              className="h-7 text-xs font-mono"
            />
            <p className="text-[11px] text-muted-foreground">{t("chatIdDesc")}</p>
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="telegram-message-template">
              {t("messageTemplate")}
            </Label>
            <Input
              id="telegram-message-template"
              name="telegram-message-template"
              value={config.message_template}
              onChange={(e) => update("message_template", e.target.value)}
              placeholder="<b>{title}</b>\n{message}"
              className="h-7 text-xs font-mono"
            />
            <p className="text-[11px] text-muted-foreground">{t("messageTemplateDesc")}</p>
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="telegram-included-fields">
              {t("includedFields")}
            </Label>
            <Input
              id="telegram-included-fields"
              name="telegram-included-fields"
              value={config.included_fields.join(", ")}
              onChange={(e) =>
                update(
                  "included_fields",
                  e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean)
                )
              }
              placeholder="severity, source_ip"
              className="h-7 text-xs font-mono"
            />
            <p className="text-[11px] text-muted-foreground">{t("includedFieldsDesc")}</p>
          </div>
        </div>
      </div>

      <Separator />

      <div className="space-y-1.5 pt-1">
        <p className="text-[11px] text-muted-foreground font-medium">Payload Preview</p>
        <div className="rounded-md border border-border bg-[#1e1e1e] overflow-hidden">
          <SyntaxHighlighter
            language="json"
            style={vs2015}
            customStyle={{
              margin: 0,
              padding: "0.625rem 0.75rem",
              background: "transparent",
              fontSize: "11px",
              lineHeight: "1.6",
            }}
            wrapLines={false}
          >
            {JSON.stringify(previewPayload, null, 2)}
          </SyntaxHighlighter>
        </div>
      </div>

      <Separator />

      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant="secondary"
          onClick={handleTest}
          disabled={testState === "loading" || saving}
          className="h-7 text-xs gap-1.5"
        >
          <Send className="h-3 w-3" />
          {t("sendTestNotification")}
        </Button>
        {testState !== "idle" && (
          <span
            className={cn(
              "flex items-center gap-1 text-xs",
              testState === "ok" ? "text-green-600" : "text-destructive"
            )}
          >
            {testState === "ok" ? <CheckCircle2 className="h-3 w-3" /> : testState === "err" ? <AlertCircle className="h-3 w-3" /> : null}
            {testMsg || (testState === "loading" ? t("sending") : "")}
          </span>
        )}
      </div>
    </div>
  );
}
