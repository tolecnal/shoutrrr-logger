"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Send } from "lucide-react";
import type { PluginConfigProps } from "../types";
import { useState } from "react";
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
  const url = (config.url as string) ?? "";
  const method = (config.method as string) ?? "POST";
  const headers = (config.headers as string) ?? '{"Content-Type": "application/json"}';
  const payloadTemplate = (config.payload_template as string) ?? '{"title": "{title}", "message": "{message}"}';
  const tlsVerification = config.tls_verification !== undefined ? (config.tls_verification as boolean) : true;

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
          <Label htmlFor="webhook-url">Webhook URL</Label>
          <Input
            id="webhook-url"
            name="webhook-url"
            placeholder="https://example.com/webhook"
            value={url}
            onChange={(e) => onChange({ ...config, url: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            The destination URL for the HTTP request.
          </p>
        </div>
        <div className="sm:col-span-1 space-y-1.5">
          <Label>Method</Label>
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
          <Label>TLS Verification</Label>
          <p className="text-xs text-muted-foreground">
            Verify the SSL/TLS certificate of the destination endpoint. Disable only for trusted internal networks.
          </p>
        </div>
        <Switch
          checked={tlsVerification}
          onCheckedChange={(checked) => onChange({ ...config, tls_verification: checked })}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="webhook-headers">Headers (JSON)</Label>
        <Textarea
          id="webhook-headers"
          name="webhook-headers"
          rows={3}
          value={headers}
          onChange={(e) => onChange({ ...config, headers: e.target.value })}
          className="font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          Custom HTTP headers defined as a JSON object.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="webhook-payload-template">Payload Template</Label>
          <Textarea
            id="webhook-payload-template"
            name="webhook-payload-template"
            rows={10}
            value={payloadTemplate}
            onChange={(e) => onChange({ ...config, payload_template: e.target.value })}
            className="font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">
            The payload sent in the request body. Variables like {"{title}"}, {"{message}"}, and {"{severity}"} will be replaced. 
            Use {"{custom_fields.your_key}"} for custom fields. Values will be escaped for JSON injection if necessary.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label>Payload Preview</Label>
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
            Example payload generated from your template.
          </p>
        </div>
      </div>

      <div className="pt-2 border-t flex items-center justify-between">
        <div className="text-sm">
          {testError && <span className="text-destructive">Test failed: {testError}</span>}
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleTest}
          disabled={testing || saving || !url}
          className="gap-2"
        >
          <Send className="h-4 w-4" />
          {testing ? "Sending..." : "Send Test Notification"}
        </Button>
      </div>
    </div>
  );
}
