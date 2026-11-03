"use client";
import { useState } from "react";
type Group = Record<string, any>;
const LABEL: Record<string, string> = { scan: "Scanner (markets, frequency, price-drop thresholds)", cls: "Classification (quality requirements)", alerts: "Notifications", weights: "Scoring weights" };
function Fields({ v, path, set }: { v: any; path: string[]; set: (p: string[], x: any) => void }) {
  if (v !== null && typeof v === "object" && !Array.isArray(v))
    return <div className="pl-3 border-l space-y-2" style={{ borderColor: "var(--line)" }}>{Object.entries(v).map(([k, x]) => <div key={k}><div className="text-xs mute">{k}</div><Fields v={x} path={[...path, k]} set={set} /></div>)}</div>;
  if (Array.isArray(v)) return <input className="w-full" value={v.join(",")} onChange={(e) => set(path, e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} />;
  if (typeof v === "number") return <input type="number" step="any" value={v} onChange={(e) => set(path, Number(e.target.value))} />;
  return <input value={String(v)} onChange={(e) => set(path, e.target.value)} />;
}
export default function SettingsForm({ initial }: { initial: Record<string, Group> }) {
  const [s, setS] = useState(initial); const [msg, setMsg] = useState<Record<string, string>>({});
  const set = (g: string) => (p: string[], x: any) => setS((o) => { const c = structuredClone(o); let t: any = c[g]; p.slice(0, -1).forEach((k) => (t = t[k])); t[p.at(-1)!] = x; return c; });
  async function save(g: string) {
    const r = await fetch(`/api/proxy/settings/${g}`, { method: "PUT", body: JSON.stringify(s[g]) });
    const text = r.ok ? "Saved. Applies from the next scan." : "Rejected: " + JSON.stringify((await r.json()).detail);
    setMsg((m) => ({ ...m, [g]: text }));
  }
  return <div className="space-y-6">{Object.keys(s).map((g) => (
    <section key={g} className="panel p-4 space-y-3"><h2 className="font-semibold">{LABEL[g] ?? g}</h2><Fields v={s[g]} path={[]} set={set(g)} />
      <button onClick={() => save(g)}>Save</button> <span className="text-sm mute">{msg[g]}</span></section>))}</div>;
}
