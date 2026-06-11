"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { X, Send } from "lucide-react";
import type { PluginConfigProps } from "../types";
import { useState } from "react";

export function SlackConfigPanel({
  config,
  onChange,
  onTest,
  saving,
  availableCustomFields,
}: PluginConfigProps) {
  const url = (config.webhook_url as string) ?? "";
  const messageTemplate = (config.message_template as string) ?? "*{title}*\n{message}";
  const includedFields = (config.included_fields as string[]) ?? ["received_at", "source_ip", "severity"];
  const emoji = (config.emoji as string) ?? ":rotating_light:";

  const [testError, setTestError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  const [newField, setNewField] = useState("");

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
        <Label>Webhook URL</Label>
        <Input
          placeholder="https://hooks.slack.com/services/..."
          value={url}
          onChange={(e) => onChange({ ...config, webhook_url: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          The Incoming Webhook URL from your Slack App or Integration settings.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Message Template</Label>
          <Textarea
            rows={4}
            value={messageTemplate}
            onChange={(e) => onChange({ ...config, message_template: e.target.value })}
            className="font-mono text-xs"
          />
          <p className="text-xs text-muted-foreground">
            Slack markdown supported. Use {"{title}"}, {"{message}"}, {"{severity}"}, etc. to inject notification fields.
            For custom fields, use {"{custom_fields.your_key}"}.
          </p>
        </div>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label>Emoji Icon</Label>
            <Input
              value={emoji}
              onChange={(e) => onChange({ ...config, emoji: e.target.value })}
              placeholder=":rotating_light:"
            />
            <p className="text-xs text-muted-foreground">
              Optional Slack emoji code to use as the avatar (e.g., :rotating_light: or :warning:).
            </p>
          </div>

          <div className="space-y-1.5">
            <Label>Included Fields (Attachments)</Label>
            <div className="flex flex-wrap gap-1 mb-1.5 min-h-[28px] p-2 border rounded-md bg-muted/20">
              {includedFields.length === 0 && (
                <span className="text-xs text-muted-foreground italic px-1">No additional fields</span>
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
              placeholder="Add a field e.g. tags, source_ip (press Enter)"
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

      {/* Preview box */}
      <div className="mt-6 border rounded-lg overflow-hidden">
        <div className="bg-muted px-4 py-2 border-b">
          <p className="text-xs font-medium text-muted-foreground">Slack Message Preview</p>
        </div>
        <div className="p-4 bg-background flex gap-3">
          <div className="w-9 h-9 rounded bg-muted flex items-center justify-center shrink-0 text-xl" title="Emoji">
            🚨
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline gap-2 mb-1">
              <span className="font-bold text-[15px]">shoutrrr-logger</span>
              <span className="text-xs text-muted-foreground">8:00 AM</span>
            </div>
            <div className="text-[15px] whitespace-pre-wrap">
              <strong>Preview Notification</strong>
              <br />
              This is what your message might look like in Slack.
            </div>
            {includedFields.length > 0 && (
              <div className="mt-2 border-l-4 border-[#e3e4e6] pl-3 py-1 flex gap-x-8 gap-y-2 flex-wrap">
                {includedFields.map((field) => (
                  <div key={field} className="text-sm">
                    <div className="font-bold text-muted-foreground mb-0.5">{field}</div>
                    <div>Value</div>
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
