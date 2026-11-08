import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { createHash, timingSafeEqual } from "crypto";
import { COOKIE, makeToken } from "@/lib/session";

const fails = new Map<string, { n: number; until: number }>(); // per-instance throttle (best effort on serverless)
const h = (s: string) => createHash("sha256").update(s).digest();

async function login(form: FormData) {
  "use server";
  const secret = process.env.DASHBOARD_SESSION_SECRET, pw = process.env.DASHBOARD_PASSWORD;
  if (!secret || !pw) redirect("/login?e=config");
  const f = fails.get("g") ?? { n: 0, until: 0 };
  if (Date.now() < f.until) redirect("/login?e=wait");
  if (!timingSafeEqual(h(String(form.get("password") ?? "")), h(pw!))) {
    fails.set("g", { n: f.n + 1, until: f.n + 1 >= 5 ? Date.now() + 60_000 : 0 });
    redirect("/login?e=bad");
  }
  fails.delete("g");
  (await cookies()).set(COOKIE, await makeToken(secret!), { httpOnly: true, secure: process.env.DASHBOARD_COOKIE_SECURE !== "false", sameSite: "strict", path: "/", maxAge: 43200 });
  redirect("/");
}

export default async function Login({ searchParams }: { searchParams: Promise<{ e?: string }> }) {
  const { e } = await searchParams;
  const msg = { bad: "Wrong password.", wait: "Too many attempts. Wait a minute.", config: "Server not configured (DASHBOARD_PASSWORD / DASHBOARD_SESSION_SECRET)." }[e ?? ""];
  return (
    <main className="min-h-screen grid place-items-center p-4">
      <form action={login} className="panel p-6 w-full max-w-sm space-y-4">
        <h1 className="text-lg font-semibold">Opportunity Radar</h1>
        <input name="password" type="password" autoComplete="current-password" placeholder="Password" className="w-full" required />
        {msg && <p className="text-sm text-red-400">{msg}</p>}
        <button className="w-full">Sign in</button>
      </form>
    </main>
  );
}
