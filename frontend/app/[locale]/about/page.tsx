"use client";

import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { redirectToLogin } from "@/lib/api";
import { VersionPage } from "@/components/version-page";
import { Spinner } from "@/components/ui/spinner";

export default function AboutPage() {
  const { user, isLoading } = useAuth();

  useEffect(() => {
    if (!isLoading && !user) {
      redirectToLogin();
    }
  }, [user, isLoading]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user) return null;

  return <VersionPage />;
}
