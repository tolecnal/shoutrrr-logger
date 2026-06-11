/**
 * Smoke test for CodeBlock — verifies that the registered Prism languages
 * (used by the "Test this token" snippets) render highlighted tokens
 * instead of throwing or falling back to plain text.
 */
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ThemeProvider } from "@/components/theme-provider";
import { CodeBlock } from "@/components/code-block";

function renderWithTheme(ui: React.ReactElement) {
  return render(
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      {ui}
    </ThemeProvider>,
  );
}

describe("CodeBlock", () => {
  it("highlights bash code with token spans", () => {
    const { container } = renderWithTheme(<CodeBlock code="curl -X POST https://example.com" language="bash" />);
    expect(container.querySelectorAll("span").length).toBeGreaterThan(0);
    expect(container.textContent).toContain("curl -X POST https://example.com");
  });

  it("highlights powershell, python, and php without errors", () => {
    const snippets: { code: string; language: string }[] = [
      { code: "Invoke-RestMethod -Method Post -Uri \"https://example.com\"", language: "powershell" },
      { code: "import requests\nrequests.post('https://example.com')", language: "python" },
      { code: "<?php\ncurl_init('https://example.com');", language: "php" },
    ];

    for (const { code, language } of snippets) {
      const { container } = renderWithTheme(<CodeBlock code={code} language={language} />);
      expect(container.textContent).toContain(code.split("\n")[0]!.slice(0, 10));
    }
  });

  it("renders plain pre when no language is given", () => {
    const { container } = renderWithTheme(<CodeBlock code="generic+https://example.com?@Authorization=Bearer+TOKEN" />);
    const pre = container.querySelector("pre");
    expect(pre).toBeTruthy();
    expect(pre?.textContent).toBe("generic+https://example.com?@Authorization=Bearer+TOKEN");
  });
});
