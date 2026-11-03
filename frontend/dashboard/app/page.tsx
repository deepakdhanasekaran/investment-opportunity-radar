import Link from "next/link";
import { api, pct, num } from "@/lib/api";
import Badge from "@/components/Badge";

export default async function Overview() {
  const o = await api("/api/overview");
  if (!o) return <p className="text-red-400">API unreachable or token rejected.</p>;
  return (
    <>
      <h1 className="text-xl font-semibold">Overview</h1>
      <div className="grid sm:grid-cols-3 gap-4">
        {Object.entries<any>(o.markets).map(([m, v]) => (
          <div key={m} className="panel p-4"><div className="mute text-xs">{m} market</div><div className="font-semibold">{v.open ? "Open" : "Closed"}</div>
            <div className="text-xs mute mt-1">{v.last_run ? `Last scan ${new Date(v.last_run.at).toLocaleTimeString()}: ${v.last_run.scanned} scanned, ${v.last_run.failed} failed, ${v.last_run.candidates} candidates (${v.last_run.status})` : "No scan yet"}</div></div>))}
        <div className="panel p-4"><div className="mute text-xs">Active opportunities (24h)</div><div className="text-2xl font-semibold">{o.active_opportunities}</div></div>
      </div>
      <section><h2 className="font-semibold mb-2">Highest-ranked candidates</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-sm"><tbody>
          {o.top.map((r: any) => <tr key={r.symbol}><td><Link className="underline" href={`/company/${r.symbol}`}>{r.name}</Link></td><td>{pct(r.daily_change_pct)}</td><td>Q {num(r.quality_score)}</td><td>O {num(r.opportunity_score)}</td><td><Badge c={r.classification} /></td></tr>)}
          {!o.top.length && <tr><td className="mute">None right now.</td></tr>}</tbody></table></div></section>
      <section><h2 className="font-semibold mb-2">Data providers</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-sm"><tbody>
          {o.providers.map((p: any) => <tr key={p.provider}><td>{p.provider}</td><td>{p.consecutive_failures ? <span className="text-red-400">{p.consecutive_failures} consecutive failures</span> : "healthy"}</td><td className="mute">last ok {p.last_success ? new Date(p.last_success).toLocaleString() : "never"}</td><td className="mute">{p.last_error}</td></tr>)}
          {!o.providers.length && <tr><td className="mute">No provider calls yet.</td></tr>}</tbody></table></div></section>
      <section><h2 className="font-semibold mb-2">Recent alerts</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-sm"><tbody>
          {o.alerts.map((a: any, i: number) => <tr key={i}><td className="mute">{new Date(a.at).toLocaleString()}</td><td>{a.kind}</td><td>{a.status}</td><td className="whitespace-normal">{a.message.split("\n")[0]}</td></tr>)}
          {!o.alerts.length && <tr><td className="mute">None.</td></tr>}</tbody></table></div></section>
    </>
  );
}
