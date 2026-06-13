# Translating Shoutrrr Logger

We use `next-intl` to handle internationalization in our Next.js frontend.
Translations are stored in JSON files located in `frontend/messages/`.

## How to add a new language

1. **Create the translation file**:
   Create a new JSON file in `frontend/messages/` named with the locale code (e.g., `es.json` for Spanish, `fr.json` for French). You can copy the contents of `en.json` to get started.

2. **Translate the keys**:
   Open your newly created file and translate all the values to the target language. Do not change the keys (e.g., keep `"dashboard"`, but change its value).

3. **Register the new language**:
   Open `frontend/i18n/routing.ts` and add your locale code to the `locales` array:
   ```typescript
   export const routing = defineRouting({
     locales: ['en', 'es', 'fr', 'de', 'no'], // Add yours here
     defaultLocale: 'en'
   });
   ```

4. **Update the Proxy**:
   Open `frontend/proxy.ts` and update the `matcher` array to include your new locale code in the regex path:
   ```typescript
   export const config = {
     matcher: ['/', '/(en|es|fr|de|no)/:path*', '/((?!api|_next|_vercel|.*\\..*).*)']
   };
   ```

5. **Update the Locale Switcher** (if applicable):
   If we have a language switcher component, add the new language to its options so users can select it from the UI. Also, make sure to add its display name to all language files under the `LocaleSwitcher` namespace in `frontend/messages/*.json`.

## 2. Plugin Translations

Plugins are self-contained and keep their translations inside their respective folders (e.g., `frontend/plugins/splunk/locales/`). 

To translate a plugin:
1. Add or edit your language file inside the plugin's `locales` folder (e.g., `frontend/plugins/slack/locales/no.json`).
2. Make sure the file exports a flat JSON structure with translation strings for the plugin config panel.
3. Include translations for `"name"` and `"description"`, which will override the English metadata returned by the backend.

The Next.js i18n setup (`frontend/i18n/request.ts`) automatically loads these plugin files and merges them into the global messages tree under `Plugin_<id>`.

## 3. Usage in Code (For Developers)

If you're adding new features and need to output text to the UI, you must use the translation function.

**Server Components:**
```typescript
import { getTranslations } from 'next-intl/server';

export default async function MyComponent() {
  const t = await getTranslations('MyNamespace');
  return <h1>{t('title')}</h1>;
}
```

**Client Components:**
```typescript
'use client';
import { useTranslations } from 'next-intl';

export default function MyComponent() {
  const t = useTranslations('MyNamespace');
  return <button>{t('submit')}</button>;
}
```

Please add any new keys to `frontend/messages/en.json` and optionally to other languages if you can.
