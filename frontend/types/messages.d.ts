// Compile-time message typing for next-intl (v4 AppConfig augmentation).
//
// Makes `useTranslations("NS")` / `getTranslations(...)` and the returned
// `t('key')` accept only keys that actually exist in the source-of-truth
// English catalogs. Referencing a missing/typo'd key becomes a `tsc` error.
//
// `en.json` is the base catalog. Plugin catalogs are merged at runtime under
// `Plugin_<id>` (see i18n/request.ts), so they are intersected here too — add a
// line per plugin when a new one ships with its own `locales/en.json`.

import "next-intl";

type AppMessages = typeof import("../messages/en.json") & {
  Plugin_slack: typeof import("../plugins/slack/locales/en.json");
  Plugin_splunk: typeof import("../plugins/splunk/locales/en.json");
  Plugin_webhook: typeof import("../plugins/webhook/locales/en.json");
  Plugin_ntfy: typeof import("../plugins/ntfy/locales/en.json");
  Plugin_pushover: typeof import("../plugins/pushover/locales/en.json");
  Plugin_discord: typeof import("../plugins/discord/locales/en.json");
  Plugin_telegram: typeof import("../plugins/telegram/locales/en.json");
  Plugin_gotify: typeof import("../plugins/gotify/locales/en.json");
  Plugin_pagerduty: typeof import("../plugins/pagerduty/locales/en.json");
};

declare module "next-intl" {
  interface AppConfig {
    Messages: AppMessages;
  }
}
