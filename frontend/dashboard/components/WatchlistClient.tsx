"use client";
import { useState } from "react";
type W = { symbol: string; name: string; market: string; alerts_enabled: boolean };
export default function WatchlistClient({ initial }: { initial: W[] }) {
  const [items, setItems] = useState(initial);
  const [sym, setSym] = useState(""); const [mk, setMk] = useState("SE"); const [err, setErr] = useState("");
  const reload = async () => setItems(await (await fetch("/api/proxy/watchlist")).json());
  async function add(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    const r = await fetch("/api/proxy/watchlist", { method: "POST", body: JSON.stringify({ symbol: sym, market: mk }) });
    if (!r.ok) { setErr(JSON.stringify((await r.json()).detail)); return; }
    setSym(""); reload();
  }
  async function del(s: string) { await fetch(`/api/proxy/watchlist/${encodeURIComponent(s)}`, { method: "DELETE" }); reload(); }
  return (
    <div className="space-y-4">
      <form onSubmit={add} className="flex gap-2 flex-wrap"><input value={sym} onChange={(e) => setSym(e.target.value)} placeholder="e.g. VOLV B or AAPL" required />
        <select value={mk} onChange={(e) => setMk(e.target.value)}><option>SE</option><option>US</option></select><button>Add</button></form>
      {err && <p className="text-red-400 text-sm">{err}</p>}
      <div className="panel overflow-x-auto"><table className="w-full text-sm"><tbody>
        {items.map((w) => <tr key={w.symbol}><td><a className="underline" href={`/company/${w.symbol}`}>{w.symbol}</a></td><td>{w.name}</td><td>{w.market}</td><td><button onClick={() => del(w.symbol)}>Remove</button></td></tr>)}
        {!items.length && <tr><td className="mute">Empty. Watchlist stocks are scanned in addition to the index universes.</td></tr>}</tbody></table></div>
    </div>
  );
}
