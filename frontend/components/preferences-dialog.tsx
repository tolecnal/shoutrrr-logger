"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Settings, Plus, Trash2, GripVertical, Key, Copy, Check, FlaskConical, Mail } from "lucide-react";
import useSWR from "swr";
import { toast } from "sonner";
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
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from "@/components/ui/accordion";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { TokenTestDialog } from "@/components/token-test-dialog";
import {
  fetchMyTokens,
  createMyToken,
  deleteMyToken,
  updateMyToken,
  fetchSettings,
  settingsToMap,
  fetchAlertRules,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
  testAlertRule,
  testAlertEmail
} from "@/lib/api";
import { usePreferences, type TimeFormat } from "@/lib/use-preferences";
import {
  useTagRules,
  TAG_COLOR_CLASSES,
  type TagColor,
  type TagRule,
} from "@/lib/use-tag-rules";
import { UserPluginsTab } from "@/components/user-plugins-tab";

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
      <div className="flex flex-wrap items-center gap-2 p-3">
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
          <SelectTrigger className="h-7 w-28 text-xs bg-input shrink-0">
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

function AlertRuleRow({
  rule,
  onUpdate,
  onDelete,
  onTestRule,
  onTestEmail,
  isTestingRule,
  isTestingEmail,
  testResult
}: {
  rule: import("@/lib/types").AlertRuleOut;
  onUpdate: (patch: Partial<import("@/lib/types").AlertRuleOut>) => Promise<void>;
  onDelete: () => void;
  onTestRule: (rule: import("@/lib/types").AlertRuleOut) => void;
  onTestEmail: (rule: import("@/lib/types").AlertRuleOut, notificationId?: string) => void;
  isTestingRule: boolean;
  isTestingEmail: boolean;
  testResult: { matches: import("@/lib/types").NotificationOut[]; total: number } | null | undefined;
}) {
  const [draft, setDraft] = useState(rule);
  const [saving, setSaving] = useState(false);

  useEffect(() => setDraft(rule), [rule]);

  const hasChanges = JSON.stringify(draft) !== JSON.stringify(rule);

  return (
    <AccordionItem value={rule.id} className="rounded-md border border-border bg-card px-3">
      <div className="flex items-center justify-between">
        <AccordionTrigger className="hover:no-underline py-3 flex-1 justify-start gap-2 text-sm font-medium">
          {draft.name || "Unnamed Rule"}
        </AccordionTrigger>
        <div className="flex items-center gap-2 shrink-0">
          {hasChanges && (
            <Button size="sm" className="h-7 px-2" onClick={async (e) => {
              e.stopPropagation();
              setSaving(true);
              try {
                await onUpdate(draft);
              } finally {
                setSaving(false);
              }
            }}>
              {saving ? "Saving..." : "Save"}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive shrink-0"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
      <AccordionContent>
        <div className="space-y-3 pl-2 pb-2">
          <div className="flex items-center gap-2">
            <Label className="text-xs text-muted-foreground w-16">Name</Label>
            <Input 
              value={draft.name} 
              onChange={(e) => setDraft(prev => ({ ...prev, name: e.target.value }))}
              className="h-7 text-xs flex-1"
              placeholder="Rule Name"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground">Match Type</Label>
              <select 
                className="h-8 text-xs bg-input rounded-md border border-border px-2"
                value={draft.match_type}
                onChange={(e) => setDraft(prev => ({ ...prev, match_type: e.target.value as any }))}
              >
                <option value="contains">Contains</option>
                <option value="exact">Exact Match</option>
                <option value="regex">RegEx</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground">Match Target</Label>
              <select 
                className="h-8 text-xs bg-input rounded-md border border-border px-2"
                value={draft.match_target}
                onChange={(e) => setDraft(prev => ({ ...prev, match_target: e.target.value as any }))}
              >
                <option value="all">Anywhere</option>
                <option value="title">Title Only</option>
                <option value="message">Message Only</option>
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground">Pattern</Label>
            <Input 
              placeholder="String or regex to match..." 
              value={draft.match_pattern}
              onChange={(e) => setDraft(prev => ({ ...prev, match_pattern: e.target.value }))}
              className="h-8 text-xs bg-input"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground">Scope</Label>
              <select 
                className="h-8 text-xs bg-input rounded-md border border-border px-2"
                value={draft.notification_scope}
                onChange={(e) => setDraft(prev => ({ ...prev, notification_scope: e.target.value as any }))}
              >
                <option value="all">All Notifications</option>
                <option value="global_only">Global Only</option>
                <option value="personal_only">Personal Only</option>
              </select>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Switch
                checked={draft.send_email}
                onCheckedChange={(v) => setDraft(prev => ({ ...prev, send_email: v }))}
                id={`email-${draft.id}`}
              />
              <Label htmlFor={`email-${draft.id}`} className="text-xs text-muted-foreground">Send Email Alert</Label>
            </div>
          </div>
          <div className="pt-2 border-t mt-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs gap-1 hover:text-foreground"
                  onClick={() => onTestRule(draft)}
                  disabled={isTestingRule || !draft.match_pattern}
                >
                  <FlaskConical className="h-3 w-3" />
                  {isTestingRule ? "Testing..." : "Test Rule Match"}
                </Button>
                {draft.send_email && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs gap-1 hover:text-foreground"
                    onClick={() => onTestEmail(draft)}
                    disabled={isTestingEmail || !draft.match_pattern}
                  >
                    <FlaskConical className="h-3 w-3" />
                    {isTestingEmail ? "Sending..." : "Test Email Alert"}
                  </Button>
                )}
              </div>
              {testResult !== undefined && testResult !== null && (
                <span className="text-xs text-muted-foreground">
                  {testResult.total === 0 ? "No matches found" : `Found ${testResult.total} match(es)`}
                </span>
              )}
            </div>
            {testResult && testResult.total > 0 && (
              <div className="mt-2 space-y-2">
                {testResult.matches.slice(0, 3).map(n => (
                  <div key={n.id} className="bg-background border rounded px-2 py-1.5 text-xs flex items-center justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{n.title || "No title"}</div>
                      <div className="text-muted-foreground truncate">{n.message}</div>
                    </div>
                    {draft.send_email && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground shrink-0"
                        onClick={() => onTestEmail(draft, n.id)}
                        title="Send test email with this notification"
                        disabled={isTestingEmail}
                      >
                        <Mail className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                ))}
                {testResult.total > 3 && (
                  <p className="text-xs text-muted-foreground italic pl-1">
                    ...and {testResult.total - 3} more.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}

export function PreferencesDialog() {
  const { prefs, setPrefs } = usePreferences();
  const { rules, addRule, updateRule, deleteRule } = useTagRules();
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Personal tokens state
  const [tokenName, setTokenName] = useState("");
  const [tokenExpiry, setTokenExpiry] = useState("");
  const [tokenCreating, setTokenCreating] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [newRawToken, setNewRawToken] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: myTokens, mutate: mutateTokens } = useSWR(
    open ? "/me/tokens" : null,
    fetchMyTokens,
    { revalidateOnFocus: false },
  );

  const { data: settingsList } = useSWR(open ? "/settings" : null, fetchSettings, {
    revalidateOnFocus: false,
  });
  const privateTokensEnabled = settingsList
    ? settingsToMap(settingsList).private_tokens_enabled
    : true;

  const handleCreateToken = async () => {
    const name = tokenName.trim();
    if (!name) return;
    setTokenCreating(true);
    setTokenError(null);
    try {
      const created = await createMyToken({
        name,
        expires_at: tokenExpiry ? new Date(tokenExpiry).toISOString() : null,
      });
      setNewRawToken(created.raw_token);
      setTokenName("");
      setTokenExpiry("");
      await mutateTokens();
    } catch (e) {
      setTokenError(e instanceof Error ? e.message : "Failed to create token");
    } finally {
      setTokenCreating(false);
    }
  };

  const handleDeleteToken = async (id: string) => {
    setDeletingId(id);
    try {
      await deleteMyToken(id);
      await mutateTokens();
    } finally {
      setDeletingId(null);
    }
  };

  const handleCopyToken = () => {
    if (!newRawToken) return;
    navigator.clipboard.writeText(newRawToken);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2000);
  };


  const { data: alertRules, mutate: mutateAlertRules } = useSWR(
    open ? "/alerts/rules" : null,
    fetchAlertRules,
    { revalidateOnFocus: false }
  );

  const handleAddAlertRule = async () => {
    await createAlertRule({ 
      name: "New Alert Rule", 
      match_type: "contains", 
      match_target: "all", 
      match_pattern: "", 
      notification_scope: "all", 
      send_email: false 
    });
    await mutateAlertRules();
  };

  const [testingRule, setTestingRule] = useState<Record<string, boolean>>({});
  const [testingEmail, setTestingEmail] = useState<Record<string, boolean>>({});
  const [testResults, setTestResults] = useState<Record<string, { matches: import("@/lib/types").NotificationOut[], total: number } | null>>({});

  const handleTestAlertRule = async (rule: import("@/lib/types").AlertRuleOut) => {
    setTestingRule(prev => ({ ...prev, [rule.id]: true }));
    try {
      const res = await testAlertRule(rule);
      setTestResults(prev => ({ 
        ...prev, 
        [rule.id]: { matches: res.matched_notifications || [], total: res.total_matches || 0 } 
      }));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to test rule");
    } finally {
      setTestingRule(prev => ({ ...prev, [rule.id]: false }));
    }
  };

  const handleTestEmailAlert = async (rule: import("@/lib/types").AlertRuleOut, notificationId?: string) => {
    setTestingEmail(prev => ({ ...prev, [rule.id]: true }));
    try {
      await testAlertEmail({ ...rule, notification_id: notificationId } as any);
      toast.success("Test email sent via SMTP successfully!");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to send test email");
    } finally {
      setTestingEmail(prev => ({ ...prev, [rule.id]: false }));
    }
  };

  const handleUpdateAlertRule = async (id: string, patch: Partial<import("@/lib/types").AlertRuleOut>) => {
    // Optimistic update
    mutateAlertRules(prev => prev?.map(r => r.id === id ? { ...r, ...patch } : r), false);
    await updateAlertRule(id, patch);
    await mutateAlertRules();
  };

  const handleDeleteAlertRule = async (id: string) => {
    await deleteAlertRule(id);
    await mutateAlertRules();
  };


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

      <DialogContent className="w-[95vw] max-w-[95vw] sm:max-w-[95vw] md:max-w-6xl h-[85vh] flex flex-col bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-foreground">Preferences</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="display" className="flex-1 flex flex-col min-h-0">
          <TabsList className="flex flex-wrap bg-secondary">
            <TabsTrigger value="display" className="flex-1">Display</TabsTrigger>
            <TabsTrigger value="tags" className="flex-1">Tag Rules</TabsTrigger>
            <TabsTrigger value="alerts" className="flex-1">Alert Rules</TabsTrigger>
            <TabsTrigger value="tokens" className="flex-1">My Tokens</TabsTrigger>
            <TabsTrigger value="plugins" className="flex-1">My Plugins</TabsTrigger>
          </TabsList>

          {/* ---- Display tab ---- */}
          <TabsContent value="display" className="mt-4 flex-1 min-h-0 overflow-y-auto space-y-6">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Theme</Label>
              <p className="text-xs text-muted-foreground">
                Choose how shoutrrr-logger looks. &quot;System&quot; follows your operating system setting.
              </p>
              <Select
                value={mounted ? (theme ?? "dark") : "dark"}
                onValueChange={setTheme}
              >
                <SelectTrigger className="w-48 bg-input">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dark">Dark</SelectItem>
                  <SelectItem value="light">Light</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Separator className="bg-border" />
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

          {/* ---- Alert Rules tab ---- */}
          <TabsContent value="alerts" className="mt-4 flex flex-col min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">Alert rules</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Define which notifications should trigger a visual alert.
                </p>
              </div>
              <Button size="sm" onClick={handleAddAlertRule} className="gap-1">
                <Plus className="h-3.5 w-3.5" /> Add rule
              </Button>
            </div>

            {!alertRules && <p className="text-sm text-muted-foreground py-4">Loading rules...</p>}
            
            {alertRules?.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                No alert rules defined. Add one to receive notifications.
              </p>
            )}

            {alertRules && alertRules.length > 0 && (
              <Accordion 
                type="multiple" 
                defaultValue={alertRules.length <= 2 ? alertRules.map(r => r.id) : []}
                className="space-y-3"
              >
                {alertRules.map(rule => (
                  <AlertRuleRow
                    key={rule.id}
                    rule={rule}
                    onUpdate={async (patch) => handleUpdateAlertRule(rule.id, patch)}
                    onDelete={() => handleDeleteAlertRule(rule.id)}
                    onTestRule={handleTestAlertRule}
                    onTestEmail={handleTestEmailAlert}
                    isTestingRule={testingRule[rule.id] || false}
                    isTestingEmail={testingEmail[rule.id] || false}
                    testResult={testResults[rule.id]}
                  />
                ))}
              </Accordion>
            )}
          </TabsContent>

          {/* ---- My Tokens tab ---- */}
          <TabsContent value="tokens" className="mt-4 flex flex-col min-h-0 flex-1 space-y-4">
            {/* Reveal-once raw token banner */}
            {newRawToken && (
              <div className="rounded-md border border-yellow-500/40 bg-yellow-500/10 p-3 space-y-2">
                <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400">
                  Token created — copy it now, it will not be shown again.
                </p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded bg-black/20 px-2 py-1.5 text-xs font-mono text-foreground break-all">
                    {newRawToken}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 shrink-0"
                    onClick={handleCopyToken}
                    aria-label="Copy token"
                  >
                    {copiedToken ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <TokenTestDialog
                    token={newRawToken}
                    trigger={
                      <Button size="sm" variant="outline" className="h-6 text-xs gap-1 px-2">
                        <FlaskConical className="h-3 w-3" />
                        Test
                      </Button>
                    }
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-6 text-xs text-muted-foreground px-0"
                    onClick={() => setNewRawToken(null)}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            )}

            {/* Create form */}
            {privateTokensEnabled ? (
              <div className="space-y-2">
                <p className="text-sm font-medium">Create personal token</p>
                <p className="text-xs text-muted-foreground">
                  Personal tokens are private — only notifications sent with them are visible to you.
                </p>
                <div className="flex gap-2">
                  <Input
                    className="h-8 flex-1 text-sm bg-input"
                    placeholder="Token name"
                    value={tokenName}
                    onChange={(e) => setTokenName(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleCreateToken()}
                  />
                  <Input
                    type="date"
                    className="h-8 w-36 text-sm bg-input"
                    title="Optional expiry date"
                    value={tokenExpiry}
                    onChange={(e) => setTokenExpiry(e.target.value)}
                  />
                  <Button
                    size="sm"
                    className="h-8 shrink-0"
                    onClick={handleCreateToken}
                    disabled={!tokenName.trim() || tokenCreating}
                  >
                    <Plus className="h-3.5 w-3.5 mr-1" /> Create
                  </Button>
                </div>
                {tokenError && (
                  <p className="text-xs text-destructive">{tokenError}</p>
                )}
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                Private access tokens have been disabled by your administrator.
              </p>
            )}

            <Separator className="bg-border" />

            {/* Token list */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {!myTokens && (
                <p className="text-sm text-muted-foreground text-center py-4">Loading…</p>
              )}
              {myTokens && myTokens.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No personal tokens yet.
                </p>
              )}
              {myTokens?.map((tok) => (
                <div
                  key={tok.id}
                  className="flex items-center gap-2 rounded-md border border-border bg-card px-3 py-2"
                >
                  <Key className="h-4 w-4 text-muted-foreground shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{tok.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {tok.expires_at
                        ? `Expires ${new Date(tok.expires_at).toLocaleDateString()}`
                        : "No expiry"}
                      {tok.last_used_at
                        ? ` · Last used ${new Date(tok.last_used_at).toLocaleDateString()}`
                        : ""}
                    </p>
                  </div>
                  <Switch
                    checked={tok.is_active}
                    onCheckedChange={async (v) => {
                      await updateMyToken(tok.id, { is_active: v });
                      await mutateTokens();
                    }}
                    aria-label={`${tok.is_active ? "Deactivate" : "Activate"} ${tok.name}`}
                    className="shrink-0"
                  />
                  <TokenTestDialog
                    trigger={
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground shrink-0"
                        title="Test this token"
                      >
                        <FlaskConical className="h-3.5 w-3.5" />
                      </Button>
                    }
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive shrink-0"
                    onClick={() => handleDeleteToken(tok.id)}
                    disabled={deletingId === tok.id}
                    aria-label={`Delete ${tok.name}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
            </TabsContent>

            <TabsContent value="plugins" className="mt-0 h-full flex flex-col min-h-0">
              <UserPluginsTab />
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>
  );
}
