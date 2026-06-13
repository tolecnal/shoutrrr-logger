import {getRequestConfig} from 'next-intl/server';
import {routing} from './routing';

const PLUGINS = ['splunk', 'slack', 'webhook', 'ntfy', 'pushover', 'discord', 'telegram'];

export default getRequestConfig(async ({requestLocale}) => {
  // This typically corresponds to the `[locale]` segment
  let locale = await requestLocale;
  
  // Ensure that a valid locale is used
  if (!locale || !routing.locales.includes(locale as any)) {
    locale = routing.defaultLocale;
  }
 
  let messages;
  try {
    messages = (await import(`../messages/${locale}.json`)).default;
  } catch (error) {
    // Graceful fallback if the locale is specified in routing.locales but the file is missing
    locale = routing.defaultLocale;
    messages = (await import(`../messages/${routing.defaultLocale}.json`)).default;
  }

  // Load plugin messages
  for (const plugin of PLUGINS) {
    try {
      const pluginMessages = (await import(`../plugins/${plugin}/locales/${locale}.json`)).default;
      messages[`Plugin_${plugin}`] = pluginMessages;
    } catch (e) {
      // Ignore if plugin does not have translations for this locale
    }
  }

  return {
    locale,
    messages
  };
});
