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

export function RoutingRuleDialog({
  rule,
  onClose,
  onSaved,
}: {
  rule: any | null;
  onClose: () => void;
  onSaved: (rule: any) => void;
}) {
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
      setError("Name is required");
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
          <DialogTitle>{rule ? "Edit Routing Rule" : "Create Routing Rule"}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-1.5">
            <Label>Rule Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Production Errors" />
          </div>

          <div className="space-y-1.5">
            <Label>Severities</Label>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {severities.map((s) => (
                <Badge key={s} variant="secondary" className="pr-1 text-xs">
                  {s}
                  <button className="ml-1 text-muted-foreground hover:text-foreground" onClick={() => setSeverities(severities.filter((x) => x !== s))}><X className="h-3 w-3" /></button>
                </Badge>
              ))}
            </div>
            <Input value={sevInput} onChange={(e) => setSevInput(e.target.value)} onKeyDown={(e) => addItem(e, sevInput, setSevInput, severities, setSeverities)} placeholder="e.g. critical (press Enter)" />
          </div>

          <div className="space-y-1.5">
            <Label>Tags</Label>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {tags.map((t) => (
                <Badge key={t} variant="secondary" className="pr-1 text-xs">
                  {t}
                  <button className="ml-1 text-muted-foreground hover:text-foreground" onClick={() => setTags(tags.filter((x) => x !== t))}><X className="h-3 w-3" /></button>
                </Badge>
              ))}
            </div>
            <Input value={tagInput} onChange={(e) => setTagInput(e.target.value)} onKeyDown={(e) => addItem(e, tagInput, setTagInput, tags, setTags)} placeholder="e.g. prod (press Enter)" list="tag-suggestions" />
            <datalist id="tag-suggestions">
              {tagSuggestions.map((t) => <option key={t} value={t} />)}
            </datalist>
          </div>

          <div className="space-y-1.5">
            <Label>Tokens</Label>
            <div className="flex flex-wrap gap-1 mb-1.5">
              {tokens.map((t) => (
                <Badge key={t} variant="secondary" className="pr-1 text-xs">
                  {tokenSuggestions.find(x => x.id === t)?.name || t}
                  <button className="ml-1 text-muted-foreground hover:text-foreground" onClick={() => setTokens(tokens.filter((x) => x !== t))}><X className="h-3 w-3" /></button>
                </Badge>
              ))}
            </div>
            <select
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value=""
              onChange={(e) => {
                if (e.target.value && !tokens.includes(e.target.value)) {
                  setTokens([...tokens, e.target.value]);
                }
              }}
            >
              <option value="" disabled>Select a token...</option>
              {tokenSuggestions.map((t) => (
                <option key={t.id} value={t.id}>{t.name} {t.is_global ? "(Global)" : ""}</option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label>Custom Fields</Label>
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
              <Input className="flex-1" value={cfKeyInput} onChange={(e) => setCfKeyInput(e.target.value)} placeholder="Key" list="cf-suggestions" />
              <datalist id="cf-suggestions">
                {cfSuggestions.map((t) => <option key={t} value={t} />)}
              </datalist>
              <Input className="flex-1" value={cfValInput} onChange={(e) => setCfValInput(e.target.value)} placeholder="Value" onKeyDown={(e) => { if (e.key === "Enter") addCustomField(); }} />
              <Button type="button" variant="outline" onClick={addCustomField}>Add</Button>
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}
          
          {testResults !== null && (
            <div className="space-y-1.5 mt-4 pt-4 border-t">
              <Label>Test Results ({testResults.length} matches)</Label>
              {testResults.length === 0 ? (
                <p className="text-sm text-muted-foreground">No recent notifications match this rule.</p>
              ) : (
                <div className="flex flex-col gap-2 max-h-[150px] overflow-y-auto pr-2">
                  {testResults.map(n => (
                    <div key={n.id} className="text-xs bg-muted p-2 rounded border">
                      <div className="font-semibold truncate">{n.title || "No Title"}</div>
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
          <Button type="button" variant="secondary" onClick={handleTest} disabled={testing}>{testing ? "Testing..." : "Test Rule"}</Button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={handleSave}>Save Rule</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
