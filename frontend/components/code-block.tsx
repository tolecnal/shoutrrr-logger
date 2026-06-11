"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import SyntaxHighlighter from "react-syntax-highlighter/dist/esm/prism-light";
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash";
import powershell from "react-syntax-highlighter/dist/esm/languages/prism/powershell";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
import php from "react-syntax-highlighter/dist/esm/languages/prism/php";
import oneLight from "react-syntax-highlighter/dist/esm/styles/prism/one-light";
import vscDarkPlus from "react-syntax-highlighter/dist/esm/styles/prism/vsc-dark-plus";

SyntaxHighlighter.registerLanguage("bash", bash);
SyntaxHighlighter.registerLanguage("powershell", powershell);
SyntaxHighlighter.registerLanguage("python", python);
SyntaxHighlighter.registerLanguage("php", php);

interface CodeBlockProps {
  code: string;
  language?: string;
}

export function CodeBlock({ code, language }: CodeBlockProps) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!language) {
    return (
      <pre className="rounded-md bg-muted border border-border px-3 py-2 font-mono text-[11px] text-foreground whitespace-pre-wrap break-all">
        {code}
      </pre>
    );
  }

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <SyntaxHighlighter
        language={language}
        style={mounted && resolvedTheme === "light" ? oneLight : vscDarkPlus}
        customStyle={{ margin: 0, padding: "0.5rem 0.75rem", fontSize: "11px" }}
        codeTagProps={{ style: { fontFamily: "var(--font-mono, monospace)" } }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
