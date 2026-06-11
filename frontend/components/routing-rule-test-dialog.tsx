"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function RoutingRuleTestDialog({
  rule,
  onClose,
}: {
  rule: any;
  onClose: () => void;
}) {
  const [results, setResults] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleTest = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/routing-rules/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: rule.name,
          severities: rule.severities || [],
          tags: rule.tags || [],
          tokens: rule.tokens || [],
          custom_fields: rule.custom_fields || {},
        }),
      });
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const data = await res.json();
      setResults(data);
    } catch (err: any) {
      setError(err.message || "Failed to test rule");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Test Routing Rule: {rule.name}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            This will evaluate the rule against recent notifications in the database to see what matches.
            The number of matches returned is limited by server configuration (default 10).
          </p>

          {!results && !loading && (
            <Button onClick={handleTest}>Run Test</Button>
          )}

          {loading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Running test...
            </div>
          )}

          {error && <p className="text-sm text-destructive">{error}</p>}

          {results && (
            <div className="space-y-2">
              <h4 className="text-sm font-medium">Results ({results.length} matches found)</h4>
              <div className="max-h-[300px] overflow-y-auto space-y-2 pr-2">
                {results.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No recent notifications match this rule.</p>
                ) : (
                  results.map((n: any) => (
                    <div key={n.id} className="text-sm border rounded p-2 bg-muted/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="font-semibold">{n.title}</span>
                        <span className="text-xs text-muted-foreground">{new Date(n.received_at).toLocaleString()}</span>
                      </div>
                      <p className="text-muted-foreground line-clamp-1">{n.message}</p>
                      <div className="flex flex-wrap gap-1 mt-2">
                        <Badge variant="outline" className="text-xs">{n.severity}</Badge>
                        {n.tags?.map((t: string) => (
                          <Badge key={t} variant="secondary" className="text-xs">{t}</Badge>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div className="flex justify-end pt-2">
                <Button variant="outline" onClick={handleTest}>Run Again</Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
