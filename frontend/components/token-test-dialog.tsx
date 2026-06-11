"use client";

import { useState, type ReactNode } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import { CopyButton } from "@/components/copy-button";
import { CodeBlock } from "@/components/code-block";

const PLACEHOLDER_TOKEN = "YOUR_TOKEN";

function buildSnippets(url: string, token: string) {
  return [
    {
      label: "curl",
      language: "bash",
      code: `curl -X POST ${url} \\
  -H "Authorization: Bearer ${token}" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "Test notification", "title": "Test"}'`,
    },
    {
      label: "PowerShell",
      language: "powershell",
      code: `Invoke-RestMethod -Method Post -Uri "${url}" \`
  -Headers @{ Authorization = "Bearer ${token}" } \`
  -ContentType "application/json" \`
  -Body (@{ message = "Test notification"; title = "Test" } | ConvertTo-Json)`,
    },
    {
      label: "Python (requests)",
      language: "python",
      code: `import requests

requests.post(
    "${url}",
    headers={"Authorization": "Bearer ${token}"},
    json={"message": "Test notification", "title": "Test"},
)`,
    },
    {
      label: "PHP",
      language: "php",
      code: `$ch = curl_init("${url}");
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Authorization: Bearer ${token}",
    "Content-Type: application/json",
]);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode([
    "message" => "Test notification",
    "title" => "Test",
]));
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_exec($ch);
curl_close($ch);`,
    },
    {
      label: "wget",
      language: "bash",
      code: `wget -q -O- --method=POST \\
  --header="Authorization: Bearer ${token}" \\
  --header="Content-Type: application/json" \\
  --body-data='{"message": "Test notification", "title": "Test"}' \\
  ${url}`,
    },
    {
      label: "shoutrrr generic URL",
      language: undefined,
      code: `generic+${url}?@Authorization=Bearer+${token}`,
    },
  ];
}

export function TokenTestDialog({
  token,
  trigger,
}: {
  token?: string;
  trigger: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  const url =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/shoutrrr`
      : "https://shoutrrr-logger.example.com/api/shoutrrr";
  const snippets = buildSnippets(url, token ?? PLACEHOLDER_TOKEN);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-sm">Test this token</DialogTitle>
          <DialogDescription className="text-xs">
            {token
              ? "Copy any of the examples below to send a test notification."
              : "Replace YOUR_TOKEN with the token's raw value, then run one of the examples below."}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2 max-h-[60vh] overflow-y-auto pr-1">
          {snippets.map((snippet) => (
            <div key={snippet.label} className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">{snippet.label}</p>
              <div className="flex items-start gap-2">
                <div className="flex-1 min-w-0">
                  <CodeBlock code={snippet.code} language={snippet.language} />
                </div>
                <CopyButton value={snippet.code} className="mt-0" />
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
