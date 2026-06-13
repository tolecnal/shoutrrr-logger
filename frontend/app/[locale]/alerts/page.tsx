import { AlertsPage } from "@/components/alerts-page";
import { getTranslations } from "next-intl/server";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "Navigation" });
  return {
    title: `${t('alerts')} - shoutrrr-logger`
  };
}

export default function Page() {
  return <AlertsPage />;
}
