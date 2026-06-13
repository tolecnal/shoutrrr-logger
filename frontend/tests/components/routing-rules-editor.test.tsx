import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { RoutingRulesEditor } from "@/components/routing-rules-editor";
import { NextIntlClientProvider } from "next-intl";
import messages from "@/messages/en.json";

function renderWithIntl(ui: React.ReactElement) {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      {ui}
    </NextIntlClientProvider>
  );
}

// Mock the dialog so we don't have to test its entire SWR-dependent mounting logic here
vi.mock("@/components/routing-rule-dialog", () => ({
  RoutingRuleDialog: ({ onClose, onSaved, rule }: any) => (
    <div data-testid="mock-dialog">
      <span>{rule ? "Edit Mode" : "Create Mode"}</span>
      <button
        onClick={() =>
          onSaved({
            name: "Mocked Rule",
            severities: ["info"],
            tags: [],
            tokens: [],
            custom_fields: {},
          })
        }
      >
        Save Mock
      </button>
      <button onClick={onClose}>Close Mock</button>
    </div>
  ),
}));

describe("RoutingRulesEditor", () => {
  it("renders empty state", () => {
    renderWithIntl(<RoutingRulesEditor rules={[]} onChange={vi.fn()} />);
    expect(screen.getByText("No routing rules defined. The plugin will receive all notifications by default.")).toBeInTheDocument();
  });

  it("renders existing rules", () => {
    const rules = [
      { name: "First Rule", severities: ["error", "warning"], tags: ["prod"], tokens: [] },
      { name: "Second Rule", severities: [], tags: [], tokens: ["123"] },
    ];
    renderWithIntl(<RoutingRulesEditor rules={rules} onChange={vi.fn()} />);
    expect(screen.getByText("First Rule")).toBeInTheDocument();
    expect(screen.getByText("Severities: error, warning")).toBeInTheDocument();
    expect(screen.getByText("Tags: prod")).toBeInTheDocument();
    expect(screen.getByText("Second Rule")).toBeInTheDocument();
    expect(screen.getByText("Tokens: 1")).toBeInTheDocument();
  });

  it("allows removing a rule", () => {
    const rules = [{ name: "Rule to remove" }];
    const onChange = vi.fn();
    renderWithIntl(<RoutingRulesEditor rules={rules} onChange={onChange} />);
    
    const removeBtn = screen.getByTitle("Remove Rule");
    fireEvent.click(removeBtn);
    
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("allows opening create dialog and saving a rule", () => {
    const onChange = vi.fn();
    renderWithIntl(<RoutingRulesEditor rules={[]} onChange={onChange} />);
    
    fireEvent.click(screen.getByText("Add Rule"));
    expect(screen.getByTestId("mock-dialog")).toBeInTheDocument();
    expect(screen.getByText("Create Mode")).toBeInTheDocument();
    
    fireEvent.click(screen.getByText("Save Mock"));
    expect(onChange).toHaveBeenCalledWith([
      { name: "Mocked Rule", severities: ["info"], tags: [], tokens: [], custom_fields: {} },
    ]);
  });

  it("allows opening edit dialog and saving an updated rule", () => {
    const rules = [{ name: "Existing Rule" }];
    const onChange = vi.fn();
    renderWithIntl(<RoutingRulesEditor rules={rules} onChange={onChange} />);
    
    fireEvent.click(screen.getByTitle("Edit Rule"));
    expect(screen.getByTestId("mock-dialog")).toBeInTheDocument();
    expect(screen.getByText("Edit Mode")).toBeInTheDocument();
    
    fireEvent.click(screen.getByText("Save Mock"));
    expect(onChange).toHaveBeenCalledWith([
      { name: "Mocked Rule", severities: ["info"], tags: [], tokens: [], custom_fields: {} },
    ]);
  });
});
