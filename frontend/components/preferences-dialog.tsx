"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Settings, Plus, Trash2, GripVertical, Key, Copy, Check, FlaskConical, Mail, Pencil, Monitor, Tags, Bell, Puzzle } from "lucide-react";
import useSWR from "swr";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
  useLabelRules,
  LABEL_COLOR_CLASSES,
  type LabelColor,
  type LabelRule,
} from "@/lib/use-label-rules";
import { UserPluginsTab } from "@/components/user-plugins-tab";
import { TokenDeliveryToggles } from "@/components/token-delivery-toggles";
import { ExternalDeliveryWarning } from "@/components/external-delivery-warning";
import type { AccessTokenOut } from "@/lib/types";
import { useTranslations } from "next-intl";

const LABEL_COLORS: LabelColor[] = [
  "slate","blue","green","yellow","orange","red","purple","pink","teal",
];

function LabelBadgePreview({ color, name }: { color: LabelColor; name: string }) {
  const cls = LABEL_COLOR_CLASSES[color];
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${cls.bg} ${cls.text} ${cls.border}`}
    >
      {name || "Preview"}
    </span>
  );
}

function LabelRuleRow({
  rule,
  onUpdate,
  onDelete,
}: {
  rule: LabelRule;
  onUpdate: (patch: Partial<Omit<LabelRule, "id">>) => void;
  onDelete: () => void;
}) {
  const t = useTranslations("PreferencesDialog");
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
          title={rule.exclude ? t('excludeOn') : t('excludeOff')}
          className={cn(
            "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium border transition-colors",
            rule.exclude
              ? "bg-destructive/10 text-destructive border-destructive/40"
              : "bg-transparent text-muted-foreground border-border hover:border-foreground/30"
          )}
        >
          {t('exclude')}
        </button>
        <Select
          value={rule.color}
          onValueChange={(v) => onUpdate({ color: v as LabelColor })}
        >
          <SelectTrigger className="h-7 w-28 text-xs bg-input shrink-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {LABEL_COLORS.map((c) => (
              <SelectItem key={c} value={c}>
                <LabelBadgePreview color={c} name={c} />
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {/* Live badge preview — acts as the visible name; click "N patterns" to edit name */}
        <LabelBadgePreview color={rule.color} name={rule.name} />
        {/* Spacer to push patterns + delete to the right */}
        <span className="flex-1" />
        <button
          className="shrink-0 text-xs text-muted-foreground hover:text-foreground transition-colors"
          onClick={() => setExpanded((v) => !v)}
        >
          {t('patternsCount', { count: rule.patterns.length })}
        </button>
        <Button
          size="sm"
          variant="ghost"
          className="shrink-0 h-7 w-7 p-0 text-destructive hover:text-destructive"
          onClick={onDelete}
          aria-label={t('deleteRule')}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>

      {/* Expanded patterns editor */}
      {expanded && (
        <div className="border-t border-border px-3 pb-3 pt-2 space-y-1.5">
          {/* Name editor */}
          <div className="flex items-center gap-2 pb-1">
            <Label className="text-xs text-muted-foreground shrink-0 w-12" htmlFor={`label-rule-name-${rule.id}`}>{t('name')}</Label>
            <Input
              id={`label-rule-name-${rule.id}`}
              name={`label-rule-name-${rule.id}`}
              className="h-7 flex-1 min-w-0 text-xs"
              value={rule.name}
              placeholder={t('labelNamePlaceholder')}
              onChange={(e) => onUpdate({ name: e.target.value })}
            />
          </div>
          <p className="text-xs text-muted-foreground mb-2">
            {t('regexPatternsDesc')}
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
                aria-label={t('removePattern')}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))}
          <div className="flex items-center gap-2 pt-1">
            <Input
              id={`label-rule-pattern-${rule.id}`}
              name={`label-rule-pattern-${rule.id}`}
              className="h-7 flex-1 font-mono text-xs bg-input"
              placeholder={t('newPatternPlaceholder')}
              value={patternInput}
              onChange={(e) => setPatternInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addPattern()}
            />
            <Button size="sm" className="h-7 px-2 text-xs" onClick={addPattern}>
              <Plus className="h-3 w-3 mr-1" /> {t('add')}
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
  const t = useTranslations("PreferencesDialog");
  const [draft, setDraft] = useState(rule);
  const [saving, setSaving] = useState(false);

  useEffect(() => setDraft(rule), [rule]);

  const hasChanges = JSON.stringify(draft) !== JSON.stringify(rule);

  return (
    <AccordionItem value={rule.id} className="rounded-md border border-border bg-card px-3">
      <div className="flex items-center justify-between">
        <AccordionTrigger className="hover:no-underline py-3 flex-1 justify-start gap-2 text-sm font-medium">
          {draft.name || t('unnamedRule')}
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
              {saving ? t('saving') : t('save')}
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
            <Label className="text-xs text-muted-foreground w-16" htmlFor={`alert-rule-name-${draft.id}`}>{t('name')}</Label>
            <Input
              id={`alert-rule-name-${draft.id}`}
              name={`alert-rule-name-${draft.id}`}
              value={draft.name}
              onChange={(e) => setDraft(prev => ({ ...prev, name: e.target.value }))}
              className="h-7 text-xs flex-1"
              placeholder={t('name')}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground" htmlFor={`alert-rule-match-type-${draft.id}`}>{t('matchType')}</Label>
              <select
                id={`alert-rule-match-type-${draft.id}`}
                name={`alert-rule-match-type-${draft.id}`}
                className="h-8 text-xs bg-input rounded-md border border-border px-2"
                value={draft.match_type}
                onChange={(e) => setDraft(prev => ({ ...prev, match_type: e.target.value as any }))}
              >
                <option value="contains">{t('contains')}</option>
                <option value="exact">{t('exactMatch')}</option>
                <option value="regex">{t('regex')}</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground" htmlFor={`alert-rule-match-target-${draft.id}`}>{t('matchTarget')}</Label>
              <select
                id={`alert-rule-match-target-${draft.id}`}
                name={`alert-rule-match-target-${draft.id}`}
                className="h-8 text-xs bg-input rounded-md border border-border px-2"
                value={draft.match_target}
                onChange={(e) => setDraft(prev => ({ ...prev, match_target: e.target.value as any }))}
              >
                <option value="all">{t('anywhere')}</option>
                <option value="title">{t('titleOnly')}</option>
                <option value="message">{t('messageOnly')}</option>
              </select>
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label className="text-xs text-muted-foreground" htmlFor={`alert-rule-pattern-${draft.id}`}>{t('pattern')}</Label>
            <Input
              id={`alert-rule-pattern-${draft.id}`}
              name={`alert-rule-pattern-${draft.id}`}
              placeholder={t('patternPlaceholder')}
              value={draft.match_pattern}
              onChange={(e) => setDraft(prev => ({ ...prev, match_pattern: e.target.value }))}
              className="h-8 text-xs bg-input"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label className="text-xs text-muted-foreground" htmlFor={`alert-rule-scope-${draft.id}`}>{t('scope')}</Label>
              <select
                id={`alert-rule-scope-${draft.id}`}
                name={`alert-rule-scope-${draft.id}`}
                className="h-8 text-xs bg-input rounded-md border border-border px-2"
                value={draft.notification_scope}
                onChange={(e) => setDraft(prev => ({ ...prev, notification_scope: e.target.value as any }))}
              >
                <option value="all">{t('allNotifications')}</option>
                <option value="global_only">{t('globalOnly')}</option>
                <option value="personal_only">{t('personalOnly')}</option>
              </select>
            </div>
            <div className="flex items-center gap-2 mt-4">
              <Switch
                checked={draft.send_email}
                onCheckedChange={(v) => setDraft(prev => ({ ...prev, send_email: v }))}
                id={`email-${draft.id}`}
              />
              <Label htmlFor={`email-${draft.id}`} className="text-xs text-muted-foreground">{t('sendEmailAlert')}</Label>
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
                  {isTestingRule ? t('testing') : t('testRuleMatch')}
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
                    {isTestingEmail ? t('sending') : t('testEmailAlert')}
                  </Button>
                )}
              </div>
              {testResult !== undefined && testResult !== null && (
                <span className="text-xs text-muted-foreground">
                  {testResult.total === 0 ? t('noMatches') : t('foundMatches', { count: testResult.total })}
                </span>
              )}
            </div>
            {testResult && testResult.total > 0 && (
              <div className="mt-2 space-y-2">
                {testResult.matches.slice(0, 3).map(n => (
                  <div key={n.id} className="bg-background border rounded px-2 py-1.5 text-xs flex items-center justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium truncate">{n.title || t('noTitle')}</div>
                      <div className="text-muted-foreground truncate">{n.message}</div>
                    </div>
                    {draft.send_email && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-6 w-6 p-0 text-muted-foreground hover:text-foreground shrink-0"
                        onClick={() => onTestEmail(draft, n.id)}
                        title={t('sendTestEmailTitle')}
                        disabled={isTestingEmail}
                      >
                        <Mail className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                ))}
                {testResult.total > 3 && (
                  <p className="text-xs text-muted-foreground italic pl-1">
                    {t('andMore', { count: testResult.total - 3 })}
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
  const t = useTranslations("PreferencesDialog");
  const { prefs, setPrefs } = usePreferences();
  const { rules, addRule, updateRule, deleteRule } = useLabelRules();
  const { theme, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Personal tokens state
  const [creatingToken, setCreatingToken] = useState(false);
  const [tokenName, setTokenName] = useState("");
  const [tokenExpiry, setTokenExpiry] = useState("");
  const [tokenAllowPlugins, setTokenAllowPlugins] = useState(true);
  const [tokenAllowEmail, setTokenAllowEmail] = useState(true);
  const [tokenCreating, setTokenCreating] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [newRawToken, setNewRawToken] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Personal token edit dialog state
  const [editingToken, setEditingToken] = useState<AccessTokenOut | null>(null);
  const [editTokenName, setEditTokenName] = useState("");
  const [editTokenAllowPlugins, setEditTokenAllowPlugins] = useState(true);
  const [editTokenAllowEmail, setEditTokenAllowEmail] = useState(true);
  const [editTokenSaving, setEditTokenSaving] = useState(false);
  const [editTokenError, setEditTokenError] = useState<string | null>(null);

  const { data: myTokens, mutate: mutateTokens } = useSWR(
    open ? "/me/tokens" : null,
    fetchMyTokens,
    { revalidateOnFocus: false },
  );

  const { data: settingsList } = useSWR(open ? "/settings" : null, fetchSettings, {
    revalidateOnFocus: false,
  });
  const settingsMap = settingsList ? settingsToMap(settingsList) : null;
  const privateTokensEnabled = settingsMap ? settingsMap.private_tokens_enabled : true;
  // Admin master switch: when off, user tokens can't deliver externally, so we
  // lock the per-token toggles in the personal create/edit dialogs.
  const externalDeliveryEnabled = settingsMap ? settingsMap.user_external_delivery_enabled : true;

  const handleCreateToken = async () => {
    const name = tokenName.trim();
    if (!name) return;
    setTokenCreating(true);
    setTokenError(null);
    try {
      const created = await createMyToken({
        name,
        expires_at: tokenExpiry ? new Date(tokenExpiry).toISOString() : null,
        allow_plugin_dispatch: tokenAllowPlugins,
        allow_email_alerts: tokenAllowEmail,
      });
      setNewRawToken(created.raw_token);
      setTokenName("");
      setTokenExpiry("");
      setTokenAllowPlugins(true);
      setTokenAllowEmail(true);
      setCreatingToken(false);
      await mutateTokens();
    } catch (e) {
      setTokenError(e instanceof Error ? e.message : t('failedCreateToken'));
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

  const openTokenEdit = (tok: AccessTokenOut) => {
    setEditingToken(tok);
    setEditTokenName(tok.name);
    setEditTokenAllowPlugins(tok.allow_plugin_dispatch);
    setEditTokenAllowEmail(tok.allow_email_alerts);
    setEditTokenError(null);
  };

  const handleSaveTokenEdit = async () => {
    if (!editingToken) return;
    const name = editTokenName.trim();
    if (!name) return;
    setEditTokenSaving(true);
    setEditTokenError(null);
    try {
      const patch: {
        name?: string;
        allow_plugin_dispatch?: boolean;
        allow_email_alerts?: boolean;
      } = {};
      if (name !== editingToken.name) patch.name = name;
      if (editTokenAllowPlugins !== editingToken.allow_plugin_dispatch)
        patch.allow_plugin_dispatch = editTokenAllowPlugins;
      if (editTokenAllowEmail !== editingToken.allow_email_alerts)
        patch.allow_email_alerts = editTokenAllowEmail;
      if (Object.keys(patch).length > 0) {
        await updateMyToken(editingToken.id, patch);
        await mutateTokens();
      }
      setEditingToken(null);
    } catch (e) {
      setEditTokenError(e instanceof Error ? e.message : t('failedUpdateToken'));
    } finally {
      setEditTokenSaving(false);
    }
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
      toast.error(err instanceof Error ? err.message : t('testRuleFail'));
    } finally {
      setTestingRule(prev => ({ ...prev, [rule.id]: false }));
    }
  };

  const handleTestEmailAlert = async (rule: import("@/lib/types").AlertRuleOut, notificationId?: string) => {
    setTestingEmail(prev => ({ ...prev, [rule.id]: true }));
    try {
      await testAlertEmail({ ...rule, notification_id: notificationId } as any);
      toast.success(t('testEmailSuccess'));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t('testEmailFail'));
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
      name: "New label",
      color: "blue",
      patterns: [],
      enabled: true,
      exclude: false,
    });
  };

  return (
    <>
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
          aria-label={t('preferences')}
        >
          <Settings className="h-4 w-4" />
          {t('preferences')}
        </button>
      </DialogTrigger>

      <DialogContent className="w-[95vw] max-w-[95vw] sm:max-w-[95vw] md:max-w-6xl h-[85vh] flex flex-col bg-card border-border">
        <DialogHeader>
          <DialogTitle className="text-foreground">{t('preferences')}</DialogTitle>
        </DialogHeader>

        <Tabs defaultValue="display" className="flex-1 flex flex-col min-h-0">
          <TabsList className="flex flex-wrap bg-secondary">
            <TabsTrigger value="display" className="flex-1 gap-1.5"><Monitor className="h-3.5 w-3.5" />{t('tabs.display')}</TabsTrigger>
            <TabsTrigger value="labels" className="flex-1 gap-1.5"><Tags className="h-3.5 w-3.5" />{t('tabs.labels')}</TabsTrigger>
            <TabsTrigger value="alerts" className="flex-1 gap-1.5"><Bell className="h-3.5 w-3.5" />{t('tabs.alerts')}</TabsTrigger>
            <TabsTrigger value="tokens" className="flex-1 gap-1.5"><Key className="h-3.5 w-3.5" />{t('tabs.tokens')}</TabsTrigger>
            <TabsTrigger value="plugins" className="flex-1 gap-1.5"><Puzzle className="h-3.5 w-3.5" />{t('tabs.plugins')}</TabsTrigger>
          </TabsList>

          {/* ---- Display tab ---- */}
          <TabsContent value="display" className="mt-4 flex-1 min-h-0 overflow-y-auto space-y-6">
            <div className="space-y-2">
              <Label className="text-sm font-medium">{t('theme')}</Label>
              <p className="text-xs text-muted-foreground">
                {t('themeDesc')}
              </p>
              <Select
                value={mounted ? (theme ?? "dark") : "dark"}
                onValueChange={setTheme}
              >
                <SelectTrigger className="w-48 bg-input">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="dark">{t('themeDark')}</SelectItem>
                  <SelectItem value="light">{t('themeLight')}</SelectItem>
                  <SelectItem value="system">{t('themeSystem')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Separator className="bg-border" />
            <div className="space-y-2">
              <Label className="text-sm font-medium">{t('timeFormat')}</Label>
              <p className="text-xs text-muted-foreground">
                {t('timeFormatDesc')}
              </p>
              <Select
                value={prefs.timeFormat}
                onValueChange={(v) => setPrefs({ timeFormat: v as TimeFormat })}
              >
                <SelectTrigger className="w-48 bg-input">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="locale">{t('timeAuto')}</SelectItem>
                  <SelectItem value="24h">{t('time24h')}</SelectItem>
                  <SelectItem value="12h">{t('time12h')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Separator className="bg-border" />
            <p className="text-xs text-muted-foreground">
              {t('localStoreNotice')}
            </p>
          </TabsContent>

          {/* ---- Labels tab ---- */}
          <TabsContent
            value="labels"
            className="mt-4 flex flex-col min-h-0 flex-1 space-y-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{t('labelRules')}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('labelRulesDesc')}
                </p>
              </div>
              <Button size="sm" onClick={handleAddRule} className="gap-1">
                <Plus className="h-3.5 w-3.5" /> {t('addRule')}
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {rules.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  {t('noLabelRules')}
                </p>
              )}
              {rules.map((rule) => (
                <LabelRuleRow
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
                <p className="text-sm font-medium">{t('alertRules')}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('alertRulesDesc')}
                </p>
              </div>
              <Button size="sm" onClick={handleAddAlertRule} className="gap-1">
                <Plus className="h-3.5 w-3.5" /> {t('addRule')}
              </Button>
            </div>

            {!externalDeliveryEnabled && (
              <ExternalDeliveryWarning message={t('externalDeliveryWarningAlerts')} />
            )}

            {!alertRules && <p className="text-sm text-muted-foreground py-4">{t('loadingRules')}</p>}
            
            {alertRules?.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">
                {t('noAlertRules')}
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
            {!externalDeliveryEnabled && (
              <ExternalDeliveryWarning message={t('externalDeliveryWarningTokens')} />
            )}

            {/* Reveal-once raw token banner */}
            {newRawToken && (
              <div className="rounded-md border border-yellow-500/40 bg-yellow-500/10 p-3 space-y-2">
                <p className="text-xs font-medium text-yellow-600 dark:text-yellow-400">
                  {t('tokenCreated')}
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
                    aria-label={t('copyToken')}
                  >
                    {copiedToken ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <TokenTestDialog
                    token={newRawToken}
                    trigger={
                      <Button size="sm" variant="outline" className="h-6 text-xs gap-1 px-2 text-muted-foreground hover:text-foreground">
                        <span className="text-[10px] font-mono font-bold">{"{}"}</span>
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

            {/* Create */}
            {privateTokensEnabled ? (
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">
                  Personal tokens are private — only notifications sent with them are visible to you.
                </p>
                <Button
                  size="sm"
                  className="h-8 shrink-0 gap-1.5"
                  onClick={() => {
                    setTokenName("");
                    setTokenExpiry("");
                    setTokenAllowPlugins(true);
                    setTokenAllowEmail(true);
                    setTokenError(null);
                    setCreatingToken(true);
                  }}
                >
                  <Plus className="h-3.5 w-3.5" /> {t('createToken')}
                </Button>
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
                  {t('noTokens')}
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
                        <span className="text-[10px] font-mono font-bold">{"{}"}</span>
                      </Button>
                    }
                  />
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground shrink-0"
                    onClick={() => openTokenEdit(tok)}
                    aria-label={`Edit ${tok.name}`}
                    title={t('editToken')}
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
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
              <UserPluginsTab externalDeliveryDisabled={!externalDeliveryEnabled} />
            </TabsContent>
          </Tabs>
        </DialogContent>
      </Dialog>

      {/* Personal token create dialog */}
      <Dialog open={creatingToken} onOpenChange={(o) => !o && setCreatingToken(false)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">{t('createToken')}</DialogTitle>
            <DialogDescription className="text-xs">
              Private to you — only notifications sent with it are visible to you. The raw value
              is shown once after creation.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs" htmlFor="create-personal-token-name">{t('name')}</Label>
              <Input
                id="create-personal-token-name"
                name="create-personal-token-name"
                className="h-8 text-sm"
                placeholder={t('cliScriptPlaceholder')}
                value={tokenName}
                onChange={(e) => setTokenName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreateToken()}
                autoFocus
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs" htmlFor="create-personal-token-expiry">
                {t('expiresAt')}
              </Label>
              <Input
                id="create-personal-token-expiry"
                name="create-personal-token-expiry"
                type="date"
                className="h-8 text-sm"
                value={tokenExpiry}
                onChange={(e) => setTokenExpiry(e.target.value)}
              />
            </div>
            {!externalDeliveryEnabled && (
              <ExternalDeliveryWarning message={t('externalDeliveryWarningToggles')} />
            )}
            <TokenDeliveryToggles
              idPrefix="personal-create"
              disabled={!externalDeliveryEnabled}
              value={{
                allow_plugin_dispatch: tokenAllowPlugins,
                allow_email_alerts: tokenAllowEmail,
              }}
              onChange={(v) => {
                setTokenAllowPlugins(v.allow_plugin_dispatch);
                setTokenAllowEmail(v.allow_email_alerts);
              }}
            />
            {tokenError && <p className="text-xs text-destructive">{tokenError}</p>}
          </div>
          <DialogFooter>
            <Button size="sm" variant="secondary" onClick={() => setCreatingToken(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleCreateToken}
              disabled={tokenCreating || !tokenName.trim()}
            >
              {tokenCreating ? t('creating') : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Personal token edit dialog */}
      <Dialog open={!!editingToken} onOpenChange={(o) => !o && setEditingToken(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-sm">{t('editToken')}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs" htmlFor="edit-personal-token-name">{t('name')}</Label>
              <Input
                id="edit-personal-token-name"
                name="edit-personal-token-name"
                className="h-8 text-sm"
                value={editTokenName}
                onChange={(e) => setEditTokenName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSaveTokenEdit()}
              />
            </div>
            {!externalDeliveryEnabled && (
              <ExternalDeliveryWarning message={t('externalDeliveryWarningToggles')} />
            )}
            <TokenDeliveryToggles
              idPrefix="personal-edit"
              disabled={!externalDeliveryEnabled}
              value={{
                allow_plugin_dispatch: editTokenAllowPlugins,
                allow_email_alerts: editTokenAllowEmail,
              }}
              onChange={(v) => {
                setEditTokenAllowPlugins(v.allow_plugin_dispatch);
                setEditTokenAllowEmail(v.allow_email_alerts);
              }}
            />
            {editTokenError && <p className="text-xs text-destructive">{editTokenError}</p>}
          </div>
          <DialogFooter>
            <Button size="sm" variant="secondary" onClick={() => setEditingToken(null)}>
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSaveTokenEdit}
              disabled={editTokenSaving || !editTokenName.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
