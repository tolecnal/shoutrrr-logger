"use client";

import { useState } from "react";
import { Settings, Plus, Trash2, GripVertical } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { usePreferences, type TimeFormat } from "@/lib/use-preferences";
import {
  useTagRules,
  TAG_COLOR_CLASSES,
  type TagColor,
  type TagRule,
} from "@/lib/use-tag-rules";

const TAG_COLORS: TagColor[] = [
  "slate","blue","green","yellow","orange","red","purple","pink","teal",
];

function TagBadgePreview({ color, name }: { color: TagColor; name: string }) {
  const cls = TAG_COLOR_CLASSES[color];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls.bg} ${cls.text} ${cls.border}`}
    >
      {name || "Preview"}
    </span>
  );
}

function RuleRow({
  rule,
  onUpdate,
  onDelete,
}: {
  rule: TagRule;
  onUpdate: (patch: Partial<Omit<TagRule, "id">>) => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [patternInput, setPatternInput] = useState("");

  const addPattern = () => {
    const trimmed = patternInput.trim();
    if (!trimmed) return;
    onUpdate({ patterns: [...rule.patterns, trimmed] });
    setPatternInput("");
  };

  const removePattern = (i: number) => {
    onUpdate({ patterns: rule.patterns.filter((_, idx) => idx !== i) });
  };

  return (
    <div className="rounded-md border border-border bg-card">
      {/* Row header */}
      <div className="flex items-center gap-2 p-3 overflow-hidden">
        <GripVertical className="h-4 w-4 text-muted-foreground shrink-0 cursor-grab" />
        <Switch
          checked={rule.enabled}
          onCheckedChange={(v) => onUpdate({ enabled: v })}
          aria-label={`Enable ${rule.name}`}
          className="shrink-0"
        />
        <button
          onClick={() => onUpdate({ exclude: !rule.exclude })}
          title={rule.exclude ? "Exclude mode on — matching messages are hidden" : "Exclude mode off — click to hide matching messages"}
          className={cn(
            "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium border transition-colors",
            rule.exclude
              ? "bg-destructive/10 text-destructive border-destructive/40"
              : "bg-transparent text-muted-foreground border-border hover:border-foreground/30"
          )}
        >
          Exclude
        </button>
        <Select
          value={rule.color}
          onValueChange={(v) => onUpdate({ color: v as TagColor })}
        >
          <SelectTrigger className="h-7 w-24 text-xs bg-input shrink-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TAG_COLORS.map((c) => (
              <SelectItem key={c} value={c}>
                <TagBadgePreview color={c} name={c} />
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {/* Live badge preview — acts as the visible name; click "N patterns" to edit name */}
        <TagBadgePreview color={rule.color} name={rule.name} />
        {/* Spacer to push patterns + delete to the right */}
        <span className="flex-1" />
        <button
          className="shrink-0 text-xs text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setExpanded((v) => !v)}
        >
          {rule.patterns.length} pattern{rule.patterns.length !== 1 ? "s" : ""}
        </button>
        <Button
          size="sm"
          variant="ghost"
          className="shrink-0 h-7 w-7 p-0 text-destructive hover:text-destructive"
          onClick={onDelete}
          aria-label="Delete rule"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Expanded patterns editor */}
      {expanded && (
        <div className="border-t border-border px-3 pb-3 pt-2 space-y-1.5">
          {/* Name editor */}
          <div className="flex items-center gap-2 pb-1">
            <Label className="text-xs text-muted-foreground shrink-0 w-12">Name</Label>
            <Input
              className="h-7 flex-1 min-w-0 text-xs"
              value={rule.name}
              placeholder="Tag name"
              onChange={(e) => onUpdate({ name: e.target.value })}
            />
          </div>
          <p className="text-xs text-muted-foreground mb-2">
            Regex patterns — any match applies this tag. Use{" "}
            <code className="font-mono">(?i)</code> prefix for case-insensitive.
          </p>
          {rule.patterns.map((p, i) => (
            <div key={i} className="flex items-center gap-2">
              <code className="flex-1 rounded bg-input px-2 py-1 text-xs font-mono text-foreground truncate">
                {p}
              </code>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 w-6 p-0 text-muted-foreground hover:text-destructive"
                onClick={() => removePattern(i)}
                aria-label="Remove pattern"
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))}
          <div className="flex items-center gap-2 pt-1">
            <Input
              className="h-7 flex-1 font-mono text-xs bg-input"
              placeholder="(?i)new pattern"
              value={patternInput}
              onChange={(e) => setPatternInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addPattern()}
            />
            <Button size="sm" className="h-7 px-2 text-xs" onClick={addPattern}>
              <Plus className="h-3 w-3 mr-1" /> Add
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function PreferencesDialog() {
  const { prefs, setPrefs } = usePreferences();
  const { rules, addRule, updateRule, deleteRule } = useTagRules();
  const [open, setOpen] = useState(false);

  const handleAddRule = () => {
    addRule({
      name: "New tag",
      color: "blue",
      patterns: [],
      enabled: true,
      exclude: false,
    });
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          aria-label="Open preferences"
        >
          <Settings className="h-4 w-4" />
          Preferences
        </button>
      </DialogTrigger>

      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-foreground">Preferences</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="display" className="flex-1 flex flex-col min-h-0">
          <TabsList className="grid w-full grid-cols-2 bg-secondary">
            <TabsTrigger value="display">Display</TabsTrigger>
            <TabsTrigger value="tags">Tag Rules</TabsTrigger>
          </TabsList>

          {/* ---- Display tab ---- */}
          <TabsContent value="display" className="mt-4 space-y-6">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Time format</Label>
              <p className="text-xs text-muted-foreground">
                Override how timestamps are displayed. &quot;Auto&quot; uses your browser&apos;s language setting.
              </p>
              <Select
                value={prefs.timeFormat}
                onValueChange={(v) => setPrefs({ timeFormat: v as TimeFormat })}
              >
                <SelectTrigger className="w-48 bg-input">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="locale">Auto (browser language)</SelectItem>
                  <SelectItem value="24h">24-hour (14:05:03)</SelectItem>
                  <SelectItem value="12h">12-hour (2:05:03 pm)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Separator className="bg-border" />
            <p className="text-xs text-muted-foreground">
              Preferences are stored locally in your browser and are not synced between devices.
            </p>
          </TabsContent>

          {/* ---- Tags tab ---- */}
          <TabsContent
            value="tags"
            className="mt-4 flex flex-col min-h-0 flex-1 space-y-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Tag rules</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Rules are applied in order. A notification can match multiple tags.
                </p>
              </div>
              <Button size="sm" onClick={handleAddRule} className="gap-1">
                <Plus className="h-3.5 w-3.5" /> Add rule
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {rules.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No tag rules yet. Add one to start classifying notifications.
                </p>
              )}
              {rules.map((rule) => (
                <RuleRow
                  key={rule.id}
                  rule={rule}
                  onUpdate={(patch) => updateRule(rule.id, patch)}
                  onDelete={() => deleteRule(rule.id)}
                />
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
