// Server-side only: the API token never reaches the browser.
const base = () => process.env.RADAR_API_URL ?? "http://localhost:8000";
export async function api<T = any>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const r = await fetch(base() + path, { ...init, cache: "no-store", headers: { Authorization: `Bearer ${process.env.RADAR_API_TOKEN ?? ""}`, "Content-Type": "application/json", ...(init?.headers ?? {}) } });
    if (!r.ok) return null;
    return r.status === 204 ? (null as T) : ((await r.json()) as T);
  } catch { return null; }
}
export const pct = (v: number | null | undefined) => (v == null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`);
export const num = (v: number | null | undefined, d = 0) => (v == null ? "–" : v.toFixed(d));
export const CLS: Record<string, string> = { GREEN: "bg-emerald-600/25 text-emerald-400", YELLOW: "bg-amber-500/25 text-amber-400", RED: "bg-red-600/25 text-red-400" };
