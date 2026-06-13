import { NextRequest, NextResponse } from 'next/server';
import createMiddleware from 'next-intl/middleware';
import {routing} from './i18n/routing';

const intlMiddleware = createMiddleware(routing);

// Locales that were previously supported or may be present in cached URLs
const LEGACY_LOCALES = ['es', 'fr', 'de'];

export default function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const segment = pathname.split('/')[1];

  if (LEGACY_LOCALES.includes(segment)) {
    request.nextUrl.pathname = pathname.replace(`/${segment}`, `/${routing.defaultLocale}`);
    return NextResponse.redirect(request.nextUrl);
  }

  return intlMiddleware(request);
}

export const config = {
  // Match only internationalized pathnames
  // We exclude paths like /api, /_next, /_vercel, images, etc.
  matcher: ['/', '/(en|es|fr|de|no)/:path*', '/((?!api|_next|_vercel|.*\\..*).*)']
};
