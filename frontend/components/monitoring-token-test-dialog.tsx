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
import { CodeBlock } from "@/components/code-block";

const PLACEHOLDER_TOKEN = "YOUR_TOKEN";

function buildSnippets(url: string, token: string) {
  return [
    {
      label: "curl",
      language: "bash",
      code: `curl -X GET ${url} \\
  -H "Authorization: Bearer ${token}"`,
    },
    {
      label: "PowerShell",
      language: "powershell",
      code: `Invoke-RestMethod -Method Get -Uri "${url}" \`
  -Headers @{ Authorization = "Bearer ${token}" }`,
    },
    {
      label: "Python (requests)",
      language: "python",
      code: `import requests

response = requests.get(
    "${url}",
    headers={"Authorization": "Bearer ${token}"}
)
print(response.json())`,
    },
    {
      label: "PHP",
      language: "php",
      code: `$ch = curl_init("${url}");
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    "Authorization: Bearer ${token}"
]);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
curl_close($ch);
echo $response;`,
    },
    {
      label: "wget",
      language: "bash",
      code: `wget -q -O- --header="Authorization: Bearer ${token}" ${url}`,
    },
  ];
}

export function MonitoringTokenTestDialog({
  token,
  trigger,
}: {
  token?: string;
  trigger: ReactNode;
}) {
  const [open, setOpen] = useState(false);

  const url =
    typeof window !== "undefined"
      ? `${window.location.origin}/api/v1/monitoring/health`
      : "https://shoutrrr-logger.example.com/api/v1/monitoring/health";
  const snippets = buildSnippets(url, token ?? PLACEHOLDER_TOKEN);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-sm">Test monitoring token</DialogTitle>
          <DialogDescription className="text-xs">
            Copy one of the snippets below to verify your monitoring configuration.
            Because monitoring tokens only have read access, executing these snippets will simply return system metrics and will not alter data.
          </DialogDescription>
        </DialogHeader>

        <div className="py-2 overflow-y-auto max-h-[60vh] space-y-4 pr-1">
          {snippets.map((s, idx) => (
            <div key={idx} className="space-y-1.5">
              <span className="text-xs font-semibold text-muted-foreground ml-1">
                {s.label}
              </span>
              <CodeBlock code={s.code} language={s.language} />
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
