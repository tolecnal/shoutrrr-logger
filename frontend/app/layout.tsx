import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { Toaster } from "@/components/ui/sonner";
import { AppShell } from "@/components/app-shell";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "shoutrrr-logger",
  description: "Notification logging and management for shoutrrr",
};

export const viewport: Viewport = {
  themeColor: "#0d0f14",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="bg-background" suppressHydrationWarning>
      <body className={inter.className}>
        <AuthProvider>
          <AppShell>{children}</AppShell>
          <Toaster theme="dark" />
        </AuthProvider>
      </body>
    </html>
  );
}
