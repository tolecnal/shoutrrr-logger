"use client";

import { useState, useRef } from "react";
import { GripVertical, Plus, Trash2, Send, AlertCircle, CheckCircle2 } from "lucide-react";
import type { PluginConfigProps } from "@/plugins/types";
import type { SplunkConfig, SplunkFieldMapping } from "./types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { Light as SyntaxHighlighter } from "react-syntax-highlighter";
import jsonLang from "react-syntax-highlighter/dist/esm/languages/hljs/json";
import { vs2015 } from "react-syntax-highlighter/dist/esm/styles/hljs";

SyntaxHighlighter.registerLanguage("json", jsonLang);

/** Top-level notification fields always available for mapping. */
const NOTIFICATION_FIELDS = [
  "id",
  "message",
  "title",
  "sender_name",
  "received_at",
  "source_ip",
];

/**
 * Build a preview of the Splunk event body from the current field mappings,
 * using a representative sample notification.  Mirrors the backend
 * `_build_event` / `_resolve_field` logic so the preview is accurate.
 */
function buildPreviewPayload(
  config: SplunkConfig,
  availableCustomFields: string[]
): Record<string, unknown> {
  const sampleCustomFields: Record<string, string> = {};
  for (const k of availableCustomFields) sampleCustomFields[k] = `<${k}>`;

  const sample: Record<string, unknown> = {
    id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    sender_name: "my-service",
    title: "Deploy succeeded",
    message: "Production v0.2.0 deployed successfully.",
    received_at: 1749412800.0,
    source_ip: "10.0.0.1",
    custom_fields: sampleCustomFields,
  };

  let event: Record<string, unknown>;

  if (config.field_mappings.length === 0) {
    event = Object.fromEntries(
      Object.entries(sample).filter(([, v]) => v !== null && v !== undefined)
    );
  } else {
    event = {};
    for (const m of config.field_mappings) {
      const outKey = m.output_key.trim();
      const srcField = m.source_field.trim();
      if (!outKey || !srcField) continue;
      let value: unknown;
      if (srcField.startsWith("literal:")) {
        value = srcField.slice("literal:".length);
      } else if (srcField.startsWith("custom_fields.")) {
        const key = srcField.slice("custom_fields.".length);
        value = (sample.custom_fields as Record<string, unknown>)[key] ?? `<${key}>`;
      } else {
        value = sample[srcField];
      }
      if (value !== undefined && value !== null) event[outKey] = value;
    }
  }

  const payload: Record<string, unknown> = { event };
  if (config.index.trim()) payload.index = config.index.trim();
  if (config.source.trim()) payload.source = config.source.trim();
  if (config.sourcetype.trim()) payload.sourcetype = config.sourcetype.trim();
  return payload;
}

function toSplunkConfig(raw: Record<string, unknown>): SplunkConfig {
  return {
    hec_url: String(raw.hec_url ?? ""),
    hec_token: String(raw.hec_token ?? ""),
    index: String(raw.index ?? ""),
    source: String(raw.source ?? "shoutrrr-logger"),
    sourcetype: String(raw.sourcetype ?? "_json"),
    field_mappings: (raw.field_mappings as SplunkFieldMapping[]) ?? [],
    verify_tls: raw.verify_tls !== false,
  };
}

function FieldMappingRow({
  mapping,
  index,
  availableSources,
  isDragOver,
  onUpdate,
  onRemove,
  onDragStart,
  onDragOver,
  onDrop,
  onDragEnd,
}: {
  mapping: SplunkFieldMapping;
  index: number;
  availableSources: string[];
  isDragOver: boolean;
  onUpdate: (next: SplunkFieldMapping) => void;
  onRemove: () => void;
  onDragStart: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onDragEnd: () => void;
}) {
  const listId = `sf-list-${index}`;
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
      className={cn(
        "flex items-center gap-2 rounded px-1 transition-colors",
        isDragOver && "outline outline-2 outline-primary/50 bg-primary/5"
      )}
    >
      <GripVertical className="h-4 w-4 text-muted-foreground shrink-0 cursor-grab active:cursor-grabbing" />
      <Input
        id={`splunk-mapping-source-${index}`}
        name={`splunk-mapping-source-${index}`}
        value={mapping.source_field}
        placeholder="Source field"
        list={listId}
        onChange={(e) => onUpdate({ ...mapping, source_field: e.target.value })}
        className="h-7 text-xs font-mono flex-1 min-w-0"
      />
      <datalist id={listId}>
        {availableSources.map((f) => (
          <option key={f} value={f} />
        ))}
      </datalist>
      <span className="text-muted-foreground text-xs shrink-0">→</span>
      <Input
        id={`splunk-mapping-output-${index}`}
        name={`splunk-mapping-output-${index}`}
        value={mapping.output_key}
        placeholder="Output key"
        onChange={(e) => onUpdate({ ...mapping, output_key: e.target.value })}
        className="h-7 text-xs font-mono flex-1 min-w-0"
      />
      <button
        onClick={onRemove}
        className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
        aria-label="Remove mapping"
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

export function SplunkConfigPanel({
  config: rawConfig,
  onChange,
  onTest,
  saving,
  availableCustomFields,
}: PluginConfigProps) {
  const config = toSplunkConfig(rawConfig);
  const [testState, setTestState] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [testMsg, setTestMsg] = useState("");
  const [dragOver, setDragOver] = useState<number | null>(null);
  const dragSrc = useRef<number | null>(null);

  /** Build the full source-field datalist: notification fields + custom_fields.* + literal: hint */
  const availableSources = [
    ...NOTIFICATION_FIELDS,
    ...availableCustomFields.map((k) => `custom_fields.${k}`),
    "literal:",
  ];

  function update<K extends keyof SplunkConfig>(key: K, value: SplunkConfig[K]) {
    onChange({ ...rawConfig, [key]: value });
  }

  function updateMapping(index: number, next: SplunkFieldMapping) {
    const mappings = [...config.field_mappings];
    mappings[index] = next;
    update("field_mappings", mappings);
  }

  function removeMapping(index: number) {
    update("field_mappings", config.field_mappings.filter((_, i) => i !== index));
  }

  function addMapping() {
    update("field_mappings", [
      ...config.field_mappings,
      { source_field: "", output_key: "" },
    ]);
  }

  function moveMapping(from: number, to: number) {
    if (from === to) return;
    const next = [...config.field_mappings];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    update("field_mappings", next);
  }

  async function handleTest() {
    setTestState("loading");
    setTestMsg("");
    try {
      await onTest();
      setTestState("ok");
      setTestMsg("Test event sent successfully.");
    } catch (e: unknown) {
      setTestState("err");
      setTestMsg(e instanceof Error ? e.message : "Unknown error");
    }
  }

  const previewPayload = buildPreviewPayload(config, availableCustomFields);

  return (
    <div className="space-y-5">
      {/* HEC credentials */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-foreground">HEC endpoint</h4>
        <div className="grid gap-2">
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="splunk-hec-url">URL</Label>
            <Input
              id="splunk-hec-url"
              name="splunk-hec-url"
              value={config.hec_url}
              onChange={(e) => update("hec_url", e.target.value)}
              placeholder="https://splunk.example.com:8088/services/collector/event"
              className="h-7 text-xs font-mono"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="splunk-hec-token">HEC token</Label>
            <Input
              id="splunk-hec-token"
              name="splunk-hec-token"
              type="password"
              value={config.hec_token}
              onChange={(e) => update("hec_token", e.target.value)}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="h-7 text-xs font-mono"
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="verify-tls"
              checked={config.verify_tls}
              onCheckedChange={(v) => update("verify_tls", v)}
            />
            <Label htmlFor="verify-tls" className="text-xs text-muted-foreground cursor-pointer">
              Verify TLS certificate
            </Label>
          </div>
        </div>
      </div>

      <Separator />

      {/* Splunk metadata */}
      <div className="space-y-3">
        <h4 className="text-xs font-semibold text-foreground">Splunk metadata</h4>
        <div className="grid grid-cols-3 gap-2">
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="splunk-index">Index</Label>
            <Input
              id="splunk-index"
              name="splunk-index"
              value={config.index}
              onChange={(e) => update("index", e.target.value)}
              placeholder="main"
              className="h-7 text-xs"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="splunk-source">Source</Label>
            <Input
              id="splunk-source"
              name="splunk-source"
              value={config.source}
              onChange={(e) => update("source", e.target.value)}
              placeholder="shoutrrr-logger"
              className="h-7 text-xs"
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs" htmlFor="splunk-sourcetype">Sourcetype</Label>
            <Input
              id="splunk-sourcetype"
              name="splunk-sourcetype"
              value={config.sourcetype}
              onChange={(e) => update("sourcetype", e.target.value)}
              placeholder="_json"
              className="h-7 text-xs"
            />
          </div>
        </div>
      </div>

      <Separator />

      {/* Field mappings */}
      <div className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <h4 className="text-xs font-semibold text-foreground">Field mappings</h4>
            <p className="text-[11px] text-muted-foreground mt-0.5">
              Drag rows to reorder. Use{" "}
              <code className="font-mono">custom_fields.&lt;key&gt;</code> for custom fields
              and <code className="font-mono">literal:value</code> for constants.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={addMapping}
            className="h-6 text-xs gap-1 shrink-0"
          >
            <Plus className="h-3 w-3" />
            Add
          </Button>
        </div>

        <div className="space-y-2">
          {config.field_mappings.map((m, i) => (
            <FieldMappingRow
              key={i}
              mapping={m}
              index={i}
              availableSources={availableSources}
              isDragOver={dragOver === i}
              onUpdate={(next) => updateMapping(i, next)}
              onRemove={() => removeMapping(i)}
              onDragStart={() => { dragSrc.current = i; }}
              onDragOver={(e) => { e.preventDefault(); setDragOver(i); }}
              onDrop={(e) => {
                e.preventDefault();
                if (dragSrc.current !== null) moveMapping(dragSrc.current, i);
                dragSrc.current = null;
                setDragOver(null);
              }}
              onDragEnd={() => { dragSrc.current = null; setDragOver(null); }}
            />
          ))}
          {config.field_mappings.length === 0 && (
            <p className="text-xs text-muted-foreground italic">
              No mappings — all notification fields will be forwarded.
            </p>
          )}
        </div>

        {/* Payload preview */}
        <div className="space-y-1.5 pt-1">
          <p className="text-[11px] text-muted-foreground font-medium">
            Preview{" "}
            <span className="font-normal opacity-70">
              (sample data — reflects current mappings and metadata)
            </span>
          </p>
          <div className="rounded-md border border-border bg-[#1e1e1e] overflow-hidden">
            <SyntaxHighlighter
              language="json"
              style={vs2015}
              customStyle={{ margin: 0, padding: '0.625rem 0.75rem', background: 'transparent', fontSize: '11px', lineHeight: '1.6' }}
              wrapLines={false}
            >
              {JSON.stringify(previewPayload, null, 2)}
            </SyntaxHighlighter>
          </div>
        </div>
      </div>

      <Separator />

      {/* Test */}
      <div className="flex items-center gap-3">
        <Button
          size="sm"
          variant="outline"
          onClick={handleTest}
          disabled={testState === "loading" || saving}
          className="h-7 text-xs gap-1.5"
        >
          <Send className="h-3 w-3" />
          Send test event
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
            ) : testState === "err" ? (
              <AlertCircle className="h-3 w-3" />
            ) : null}
            {testMsg || (testState === "loading" ? "Sending…" : "")}
          </span>
        )}
      </div>
    </div>
  );
}
