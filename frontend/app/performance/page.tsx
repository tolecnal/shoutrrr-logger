"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { Spinner } from "@/components/ui/spinner";
import { ApiPerformancePanel } from "@/components/api-performance-panel";

export default function PerformancePage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) router.replace("/api/auth/login");
    if (!isLoading && user && user.role !== "admin") router.replace("/log");
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user || user.role !== "admin") return null;

  return <ApiPerformancePanel />;
}
