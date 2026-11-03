import { NextRequest, NextResponse } from "next/server";
import { COOKIE, verifyToken } from "@/lib/session";

export async function middleware(req: NextRequest) {
  if (await verifyToken(req.cookies.get(COOKIE)?.value, process.env.DASHBOARD_SESSION_SECRET)) return NextResponse.next();
  if (req.nextUrl.pathname.startsWith("/api/")) return new NextResponse("unauthorized", { status: 401 });
  return NextResponse.redirect(new URL("/login", req.url));
}
export const config = { matcher: ["/((?!login|_next/static|_next/image|favicon.ico).*)"] };
