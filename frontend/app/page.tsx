"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Spinner } from "@/components/ui/spinner";
import { Bell } from "lucide-react";

export default function HomePage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/log");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20">
        <Bell className="h-8 w-8 text-primary" />
      </div>
      <div>
        <h1 className="text-2xl font-semibold text-foreground text-balance">shoutrrr-logger</h1>
        <p className="mt-2 text-sm text-muted-foreground text-pretty max-w-xs">
          Notification logging and management for shoutrrr services. Sign in to continue.
        </p>
      </div>
      <a
        href="/api/auth/login"
        className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        Sign in with SSO
      </a>
    </div>
  );
}
