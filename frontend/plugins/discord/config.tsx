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

type DiscordConfig = {
  webhook_url: string;
  bot_username: string;
  included_fields: string[];
};

function toDiscordConfig(raw: Record<string, unknown>): DiscordConfig {
  return {
    webhook_url: String(raw.webhook_url ?? ""),
    bot_username: String(raw.bot_username ?? "Shoutrrr Logger"),
    included_fields: Array.isArray(raw.included_fields)
      ? raw.included_fields.map(String)
      : ["received_at", "source_ip", "severity"],
  };
}

export function DiscordConfigPanel({
  config: rawConfig,
  onChange,
  onTest,
  saving,
  availableCustomFields,
}: PluginConfigProps) {
  const t = useTranslations("Plugin_discord");
  const config = toDiscordConfig(rawConfig);
  const [testState, setTestState] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [testMsg, setTestMsg] = useState("");

  function update<K extends keyof DiscordConfig>(key: K, value: DiscordConfig[K]) {
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

  // Build a preview of the Discord payload
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

  const fields = [];
  for (const field of config.included_fields) {
    let val: any = undefined;
    if (field.startsWith("custom_fields.")) {
      const k = field.replace("custom_fields.", "");
      val = sampleCustomFields[k] ?? `<${k}>`;
    } else {
      val = sample[field];
    }
    if (val !== undefined) {
      fields.push({ name: field, value: String(val), inline: true });
    }
  }

  const embed: Record<string, any> = {
    color: 3447003, // info color
    title: sample.title,
    description: sample.message,
  };
  if (fields.length > 0) {
    embed.fields = fields;
  }

  const previewPayload = {
    username: config.bot_username || "Shoutrrr Logger",
    embeds: [embed],
  };

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        <div className="grid gap-2">
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="discord-webhook-url">
              {t("webhookUrl")}
            </Label>
            <Input
              id="discord-webhook-url"
              name="discord-webhook-url"
              value={config.webhook_url}
              onChange={(e) => update("webhook_url", e.target.value)}
              placeholder="https://discord.com/api/webhooks/..."
              className="h-7 text-xs font-mono"
            />
            <p className="text-[11px] text-muted-foreground">{t("webhookUrlDesc")}</p>
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="discord-bot-username">
              {t("botUsername")}
            </Label>
            <Input
              id="discord-bot-username"
              name="discord-bot-username"
              value={config.bot_username}
              onChange={(e) => update("bot_username", e.target.value)}
              placeholder="Shoutrrr Logger"
              className="h-7 text-xs"
            />
            <p className="text-[11px] text-muted-foreground">{t("botUsernameDesc")}</p>
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="discord-included-fields">
              {t("includedFields")}
            </Label>
            <Input
              id="discord-included-fields"
              name="discord-included-fields"
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
              placeholder="received_at, source_ip, severity"
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
