import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Presence-only guard: sends anonymous page loads to /login.
// The cookie is a non-secret flag set by Django; real authorization is enforced by the API.
export function proxy(request: NextRequest) {
  if (!request.cookies.has("cmrs_session")) {
    const url = new URL("/login", request.url);
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/admin/:path*", "/customers/:path*", "/loans/:path*", "/today/:path*", "/collections/:path*", "/cash/:path*", "/submissions/:path*", "/deposits/:path*", "/reports/:path*", "/trace/:path*", "/audit/:path*", "/"],
};
