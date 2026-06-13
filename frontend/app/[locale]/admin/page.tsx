"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";
import { AdminPanel } from "@/components/admin-panel";
import { Spinner } from "@/components/ui/spinner";
import { ShieldAlert } from "lucide-react";
import { useTranslations } from "next-intl";

export default function AdminPage() {
  const t = useTranslations("Admin");
  const { user, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace("/api/auth/login");
    }
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (!user) return null;

  if (user.role !== "admin") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center px-6">
        <ShieldAlert className="h-10 w-10 text-destructive" />
        <p className="text-sm text-muted-foreground">
          {t('noPermission')}
        </p>
      </div>
    );
  }

  return <AdminPanel />;
}
