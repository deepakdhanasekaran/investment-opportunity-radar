import { NextRequest, NextResponse } from "next/server";
// Authenticated (middleware) pass-through for client components. Only whitelisted prefixes are reachable.
const ALLOWED = ["watchlist", "settings"];
async function handle(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (!ALLOWED.includes(path[0]) || path.some((p) => p === ".." || p.includes("/"))) return new NextResponse("not found", { status: 404 });
  const url = `${process.env.RADAR_API_URL ?? "http://localhost:8000"}/api/${path.map(encodeURIComponent).join("/")}`;
  const body = req.method === "GET" || req.method === "DELETE" ? undefined : await req.text();
  const r = await fetch(url, { method: req.method, body, cache: "no-store", headers: { Authorization: `Bearer ${process.env.RADAR_API_TOKEN ?? ""}`, "Content-Type": "application/json" } });
  return new NextResponse(r.status === 204 ? null : await r.text(), { status: r.status, headers: { "Content-Type": "application/json" } });
}
export { handle as GET, handle as POST, handle as PUT, handle as DELETE };
