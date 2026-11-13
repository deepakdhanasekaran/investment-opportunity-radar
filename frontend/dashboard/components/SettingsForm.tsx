"use client";
import { useState } from "react";
type Group = Record<string, any>;
const LABEL: Record<string, string> = { scan: "Scanner (markets, frequency, price-drop thresholds)", cls: "Classification (quality requirements)", alerts: "Notifications", weights: "Scoring weights" };
const nice = (k: string) => (k[0].toUpperCase() + k.slice(1)).replaceAll("_", " ");
const isObj = (v: any) => v !== null && typeof v === "object" && !Array.isArray(v);
function Fields({ v, path, set }: { v: any; path: string[]; set: (p: string[], x: any) => void }) {
  if (isObj(v))
    return <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(v).map(([k, x]) => isObj(x)
      ? <fieldset key={k} className="col-span-full pl-3 border-l space-y-2" style={{ borderColor: "var(--line)" }}><legend className="text-sm font-medium pb-2">{nice(k)}</legend><Fields v={x} path={[...path, k]} set={set} /></fieldset>
      : <label key={k} className="block text-xs mute">{nice(k)}<div className="mt-1 text-sm" style={{ color: "var(--fg)" }}><Fields v={x} path={[...path, k]} set={set} /></div></label>)}</div>;
  if (Array.isArray(v)) return <input className="w-full" value={v.join(",")} onChange={(e) => set(path, e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} />;
  if (typeof v === "number") return <input className="w-full" type="number" step="any" value={v} onChange={(e) => set(path, Number(e.target.value))} />;
  return <input className="w-full" value={String(v)} onChange={(e) => set(path, e.target.value)} />;
}
export default function SettingsForm({ initial }: { initial: Record<string, Group> }) {
  const [s, setS] = useState(initial); const [msg, setMsg] = useState<Record<string, { ok: boolean; text: string }>>({}); const [busy, setBusy] = useState("");
  const set = (g: string) => (p: string[], x: any) => setS((o) => { const c = structuredClone(o); let t: any = c[g]; p.slice(0, -1).forEach((k) => (t = t[k])); t[p.at(-1)!] = x; return c; });
  async function save(g: string) {
    setBusy(g);
    try {
      const r = await fetch(`/api/proxy/settings/${g}`, { method: "PUT", body: JSON.stringify(s[g]) });
      const d = r.ok ? null : (await r.json().catch(() => null))?.detail;
      setMsg((m) => ({ ...m, [g]: r.ok ? { ok: true, text: "Saved. Applies from the next scan." } : { ok: false, text: "Rejected: " + (typeof d === "string" ? d : JSON.stringify(d ?? r.statusText)) } }));
    } catch { setMsg((m) => ({ ...m, [g]: { ok: false, text: "Could not reach the server. Nothing was saved." } })); } finally { setBusy(""); }
  }
  return <div className="space-y-6">{Object.keys(s).map((g) => (
    <section key={g} className="panel p-4 space-y-4"><h2>{LABEL[g] ?? g}</h2><Fields v={s[g]} path={[]} set={set(g)} />
      <div className="flex items-center gap-3 flex-wrap"><button className="primary" disabled={busy === g} onClick={() => save(g)}>{busy === g ? "Saving…" : "Save"}</button>
        <span className={`text-sm ${msg[g] ? (msg[g].ok ? "up" : "down") : ""}`} role="status">{msg[g]?.text}</span></div></section>))}</div>;
}
