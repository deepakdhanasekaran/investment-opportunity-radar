"use client";
import Link from "next/link";
import { useState } from "react";
type W = { symbol: string; name: string; market: string; alerts_enabled: boolean };
export default function WatchlistClient({ initial }: { initial: W[] }) {
  const [items, setItems] = useState(initial);
  const [sym, setSym] = useState(""); const [mk, setMk] = useState("SE"); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const reload = async () => setItems(await (await fetch("/api/proxy/watchlist")).json());
  async function add(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try {
      const r = await fetch("/api/proxy/watchlist", { method: "POST", body: JSON.stringify({ symbol: sym, market: mk }) });
      if (!r.ok) { const d = (await r.json()).detail; setErr(typeof d === "string" ? d : JSON.stringify(d)); return; }
      setSym(""); await reload();
    } catch { setErr("Could not reach the server. Try again."); } finally { setBusy(false); }
  }
  async function del(s: string) { setItems((xs) => xs.filter((w) => w.symbol !== s)); await fetch(`/api/proxy/watchlist/${encodeURIComponent(s)}`, { method: "DELETE" }); reload(); }
  return (
    <div className="space-y-4">
      <form onSubmit={add} className="flex gap-2 flex-wrap"><input className="flex-1 min-w-48 max-w-xs" value={sym} onChange={(e) => setSym(e.target.value)} placeholder="e.g. VOLV B or AAPL" aria-label="Ticker" required />
        <select value={mk} onChange={(e) => setMk(e.target.value)} aria-label="Market"><option>SE</option><option>US</option><option>IN</option></select><button className="primary" disabled={busy}>{busy ? "Adding…" : "Add to watchlist"}</button></form>
      {err && <p className="down text-sm" role="alert">{err}</p>}
      <div className="panel overflow-x-auto"><table className="w-full text-sm"><tbody>
        {items.map((w) => <tr key={w.symbol}><td><Link className="underline font-medium" href={`/company/${w.symbol}`}>{w.symbol}</Link></td><td>{w.name}</td><td className="mute">{w.market}</td><td className="n"><button onClick={() => del(w.symbol)} aria-label={`Remove ${w.symbol}`}>Remove</button></td></tr>)}
        {!items.length && <tr><td className="mute py-8 text-center whitespace-normal">Nothing on the watchlist yet. Stocks you add are scanned alongside the index universes.</td></tr>}</tbody></table></div>
    </div>
  );
}
