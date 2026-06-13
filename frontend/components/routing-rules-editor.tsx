"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Plus, Trash2, Edit2 } from "lucide-react";
import { RoutingRuleDialog } from "@/components/routing-rule-dialog";
import { RoutingRuleTestDialog } from "@/components/routing-rule-test-dialog";
import { Beaker } from "lucide-react";
import { useTranslations } from "next-intl";

export function RoutingRulesEditor({
  rules,
  onChange,
}: {
  rules: any[];
  onChange: (rules: any[]) => void;
}) {
  const t = useTranslations("RoutingRules");
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [testingIndex, setTestingIndex] = useState<number | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const removeRule = (index: number) => {
    const next = [...rules];
    next.splice(index, 1);
    onChange(next);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-foreground">{t('title')}</h4>
          <p className="text-xs text-muted-foreground mt-1">
            {t('description')}
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-8 shrink-0 text-xs gap-1"
          onClick={() => setIsCreating(true)}
        >
          <Plus className="h-3 w-3" />
          {t('addRule')}
        </Button>
      </div>

      <div className="space-y-2 max-h-[300px] overflow-y-auto pr-2">
        {rules.length === 0 ? (
          <p className="text-xs text-muted-foreground italic">{t('noRules')}</p>
        ) : (
          rules.map((rule, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 rounded border p-3 bg-card border-border"
            >
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium leading-none">{rule.name}</span>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  {rule.severities?.length > 0 && <span>{t('severities', { sevs: rule.severities.join(", ") })}</span>}
                  {rule.tags?.length > 0 && <span>{t('tags', { tags: rule.tags.join(", ") })}</span>}
                  {rule.tokens?.length > 0 && <span>{t('tokens', { count: rule.tokens.length })}</span>}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                  onClick={() => setEditingIndex(idx)}
                  title={t('editRule')}
                >
                  <Edit2 className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-primary"
                  onClick={() => setTestingIndex(idx)}
                  title={t('testRule')}
                >
                  <Beaker className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => removeRule(idx)}
                  title={t('removeRule')}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))
        )}
      </div>

      {isCreating && (
        <RoutingRuleDialog
          rule={null}
          onClose={() => setIsCreating(false)}
          onSaved={(newRule) => {
            onChange([...rules, newRule]);
            setIsCreating(false);
          }}
        />
      )}

      {editingIndex !== null && (
        <RoutingRuleDialog
          rule={rules[editingIndex]}
          onClose={() => setEditingIndex(null)}
          onSaved={(updatedRule) => {
            const next = [...rules];
            next[editingIndex] = updatedRule;
            onChange(next);
            setEditingIndex(null);
          }}
        />
      )}

      {testingIndex !== null && (
        <RoutingRuleTestDialog
          rule={rules[testingIndex]}
          onClose={() => setTestingIndex(null)}
        />
      )}
    </div>
  );
}
