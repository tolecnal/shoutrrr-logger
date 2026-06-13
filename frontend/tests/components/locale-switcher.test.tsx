import { render, screen, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { LocaleSwitcher } from "@/components/locale-switcher";
import { DropdownMenu, DropdownMenuContent } from "@/components/ui/dropdown-menu";
import { NextIntlClientProvider } from "next-intl";

const mockReplace = vi.fn();

vi.mock("@/i18n/routing", () => ({
  routing: {
    locales: ["en", "no"],
    defaultLocale: "en",
  },
  usePathname: () => "/log",
  useRouter: () => ({
    replace: mockReplace,
  }),
}));

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: any) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuPortal: ({ children }: any) => <div>{children}</div>,
  DropdownMenuSub: ({ children }: any) => <div>{children}</div>,
  DropdownMenuSubContent: ({ children }: any) => <div>{children}</div>,
  DropdownMenuSubTrigger: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
  DropdownMenuItem: ({ children, onClick }: any) => <button onClick={onClick}>{children}</button>,
}));

const messages = {
  LocaleSwitcher: {
    en: "English",
    no: "Norsk",
  },
};

function renderWithContext() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <LocaleSwitcher />
    </NextIntlClientProvider>
  );
}

describe("LocaleSwitcher", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    vi.clearAllMocks();
  });

  it("renders the language menu trigger", () => {
    renderWithContext();
    expect(screen.getByText("Language")).toBeInTheDocument();
  });

  it("lists available languages when rendered", async () => {
    renderWithContext();
    expect(await screen.findByText("English")).toBeInTheDocument();
    expect(await screen.findByText("Norsk")).toBeInTheDocument();
  });

  it("calls router.replace when a language is selected", async () => {
    renderWithContext();
    const noOption = await screen.findByText("Norsk");
    
    act(() => {
      fireEvent.click(noOption);
    });

    expect(mockReplace).toHaveBeenCalledWith("/log", { locale: "no" });
  });
});
