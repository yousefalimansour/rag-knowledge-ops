import { NextRequest, NextResponse } from 'next/server';

const PROTECTED_PREFIXES = ['/dashboard', '/documents', '/upload', '/search', '/copilot', '/insights', '/settings'];
const AUTH_ROUTES = ['/login', '/signup'];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const hasAccess = req.cookies.has('access_token');

  if (PROTECTED_PREFIXES.some((p) => pathname.startsWith(p)) && !hasAccess) {
    const url = req.nextUrl.clone();
    url.pathname = '/login';
    url.searchParams.set('next', pathname);
    return NextResponse.redirect(url);
  }

  if (AUTH_ROUTES.includes(pathname) && hasAccess) {
    const url = req.nextUrl.clone();
    url.pathname = '/dashboard';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/dashboard/:path*', '/documents/:path*', '/upload/:path*', '/search/:path*', '/copilot/:path*', '/insights/:path*', '/settings/:path*', '/login', '/signup'],
};
