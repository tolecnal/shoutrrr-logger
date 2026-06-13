"use client";

import { useState } from "react";
import useSWR from "swr";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { X } from "lucide-react";
import { fetchAutocompleteTags, fetchAutocompleteCustomFields, fetchAutocompleteTokens, testRoutingRule } from "@/lib/api";
import type { RoutingRuleOut, AccessTokenOut, NotificationOut } from "@/lib/types";
import { useTranslations } from "next-intl";

export function RoutingRuleDialog({
  rule,
  onClose,
  onSaved,
}: {
  rule: any | null;
  onClose: () => void;
  onSaved: (rule: any) => void;
}) {
  const t = useTranslations("RoutingRuleDialog");
  const [name, setName] = useState(rule?.name ?? "");
  const [severities, setSeverities] = useState<string[]>(rule?.severities ?? []);
  const [tags, setTags] = useState<string[]>(rule?.tags ?? []);
  const [tokens, setTokens] = useState<string[]>(rule?.tokens ?? []);
  const [customFields, setCustomFields] = useState<Record<string, string>>(rule?.custom_fields ?? {});

  const [sevInput, setSevInput] = useState("");
  const [tagInput, setTagInput] = useState("");
  const [tokenInput, setTokenInput] = useState("");
  const [cfKeyInput, setCfKeyInput] = useState("");
  const [cfValInput, setCfValInput] = useState("");

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState<NotificationOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: tagSuggestions = [] } = useSWR("/api/v1/routing-rules/autocomplete/tags", fetchAutocompleteTags);
  const { data: cfSuggestions = [] } = useSWR("/api/v1/routing-rules/autocomplete/custom-fields", fetchAutocompleteCustomFields);
  const { data: tokenSuggestions = [] } = useSWR("/api/v1/routing-rules/autocomplete/tokens", fetchAutocompleteTokens);

  const handleSave = () => {
    if (!name.trim()) {
      setError(t('nameRequired'));
      return;
    }
    setError(null);
    onSaved({ name, severities, tags, tokens, custom_fields: customFields });
  };

  const handleTest = async () => {
    setTesting(true);
    setError(null);
    try {
      const results = await testRoutingRule({ name: name || "Test Rule", severities, tags, tokens, custom_fields: customFields });
      setTestResults(results);
    } catch (e: any) {
      setError(e.message);
      setTestResults(null);
    } finally {
      setTesting(false);
    }
  };

  const addItem = (e: React.KeyboardEvent, input: string, setInput: (v: string) => void, list: string[], setList: (l: string[]) => void) => {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      const val = input.trim();
      if (!list.includes(val)) setList([...list, val]);
      setInput("");
    }
  };

  const addCustomField = () => {
    if (cfKeyInput.trim() && cfValInput.trim()) {
      setCustomFields({ ...customFields, [cfKeyInput.trim()]: cfValInput.trim() });
      setCfKeyInput("");
      setCfValInput("");
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{rule ? t('editTitle') : t('createTitle')}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-1.5">
            <Label htmlFor="rule-name">{t('ruleName')}</Label>
            <Input id="rule-name" name="rule-name" value={name} onChange={(e) => setName(e.target.value)} placeholder={t('namePlaceholder')} />
          </div>

          <div className="space-y-1.5">
            <Label>{t('severities')}</Label>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {severities.map((s) => (
                <Badge key={s} variant="secondary" className="pr-1 text-xs">
                  {s}
                  <button className="ml-1 text-muted-foreground hover:text-foreground" onClick={() => setSeverities(severities.filter((x) => x !== s))}><X className="h-3 w-3" /></button>
                </Badge>
              ))}
            </div>
            <Input id="rule-severity-input" name="rule-severity-input" value={sevInput} onChange={(e) => setSevInput(e.target.value)} onKeyDown={(e) => addItem(e, sevInput, setSevInput, severities, setSeverities)} placeholder={t('sevPlaceholder')} />
          </div>

          <div className="space-y-1.5">
            <Label>{t('tags')}</Label>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {tags.map((t) => (
                <Badge key={t} variant="secondary" className="pr-1 text-xs">
                  {t}
                  <button className="ml-1 text-muted-foreground hover:text-foreground" onClick={() => setTags(tags.filter((x) => x !== t))}><X className="h-3 w-3" /></button>
                </Badge>
              ))}
            </div>
            <Input id="rule-tag-input" name="rule-tag-input" value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => addItem(e, tagInput, setTagInput, tags, setTags)} placeholder={t('tagPlaceholder')} list="tag-suggestions" />
            <datalist id="tag-suggestions">
              {tagSuggestions.map((t) => <option key={t} value={t} />)}
            </datalist>
          </div>

          <div className="space-y-1.5">
            <Label>{t('tokens')}</Label>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {tokens.map((t) => (
                <Badge key={t} variant="secondary" className="pr-1 text-xs">
                  {tokenSuggestions.find(x => x.id === t)?.name || t}
                  <button className="ml-1 text-muted-foreground hover:text-foreground" onClick={() => setTokens(tokens.filter((x) => x !== t))}><X className="h-3 w-3" /></button>
                </Badge>
              ))}
            </div>
            <select
              id="rule-token-select"
              name="rule-token-select"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value=""
              onChange={(e) => {
                if (e.target.value && !tokens.includes(e.target.value)) {
                  setTokens([...tokens, e.target.value]);
                }
              }}
            >
              <option value="" disabled>{t('selectToken')}</option>
              {tokenSuggestions.map((tSugg) => (
                <option key={tSugg.id} value={tSugg.id}>{tSugg.name} {tSugg.is_global ? t('global') : ""}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>{t('customFields')}</Label>
            <div className="flex flex-col gap-1 mb-1.5">
              {Object.entries(customFields).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-xs bg-secondary/50 rounded px-2 py-1">
                  <span className="font-medium text-foreground">{k}:</span>
                  <span className="text-muted-foreground">{v}</span>
                  <button className="ml-auto text-muted-foreground hover:text-foreground" onClick={() => {
                    const next = { ...customFields };
                    delete next[k];
                    setCustomFields(next);
                  }}><X className="h-3 w-3" /></button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <Input id="rule-custom-field-key" name="rule-custom-field-key" className="flex-1" value={cfKeyInput} onChange={(e) => setCfKeyInput(e.target.value)} placeholder={t('key')} list="cf-suggestions" />
              <datalist id="cf-suggestions">
                {cfSuggestions.map((sugg) => <option key={sugg} value={sugg} />)}
              </datalist>
              <Input id="rule-custom-field-value" name="rule-custom-field-value" className="flex-1" value={cfValInput} onChange={(e) => setCfValInput(e.target.value)} placeholder={t('value')} onKeyDown={(e) => { if (e.key === "Enter") addCustomField(); }} />
              <Button type="button" variant="outline" onClick={addCustomField}>{t('add')}</Button>
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          
          {testResults !== null && (
            <div className="space-y-1.5 mt-4 pt-4 border-t">
              <Label>{t('testResults', { count: testResults.length })}</Label>
              {testResults.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('noMatches')}</p>
              ) : (
                <div className="flex flex-col gap-2 max-h-[150px] overflow-y-auto pr-2">
                  {testResults.map(n => (
                    <div key={n.id} className="text-xs bg-muted p-2 rounded border">
                      <div className="font-semibold truncate">{n.title || t('noTitle')}</div>
                      <div className="truncate text-muted-foreground">{n.message}</div>
                      <div className="flex gap-1 mt-1">
                        <Badge variant="outline" className="text-[10px] px-1 py-0 h-4">{n.severity}</Badge>
                        {n.tags.map(t => <Badge key={t} variant="secondary" className="text-[10px] px-1 py-0 h-4">{t}</Badge>)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="flex justify-between sm:justify-between w-full">
          <Button type="button" variant="secondary" onClick={handleTest} disabled={testing}>{testing ? t('testing') : t('testRule')}</Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>{t('cancel')}</Button>
            <Button onClick={handleSave}>{t('saveRule')}</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
