// Server-side only: the API token never reaches the browser.
const base = () => process.env.RADAR_API_URL ?? "http://localhost:8000";
export async function api<T = any>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const r = await fetch(base() + path, { ...init, cache: "no-store", headers: { Authorization: `Bearer ${process.env.RADAR_API_TOKEN ?? ""}`, "Content-Type": "application/json", ...(init?.headers ?? {}) } });
    if (!r.ok) return null;
    return r.status === 204 ? (null as T) : ((await r.json()) as T);
  } catch { return null; }
}
const r1 = (v: number) => Math.round(v * 10) / 10 || 0;  // -0.04 must not print as "-0.0%"
export const pct = (v: number | null | undefined) => (v == null ? "–" : `${r1(v) > 0 ? "+" : ""}${r1(v).toFixed(1)}%`);
export const num = (v: number | null | undefined, d = 0) => (v == null ? "–" : v.toFixed(d));
export const CLS: Record<string, string> = { GREEN: "var(--up)", YELLOW: "var(--warn)", RED: "var(--down)" };
export const tone = (v: number | null | undefined) => (v == null || Math.abs(v) < 0.05 ? "" : v > 0 ? "up" : "down");
export const when = (t: string) => new Date(t).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
