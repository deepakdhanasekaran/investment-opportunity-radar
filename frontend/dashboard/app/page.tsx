import Link from "next/link";
import { api, pct, num, tone, when } from "@/lib/api";
import Badge from "@/components/Badge";

export default async function Overview() {
  const o = await api("/api/overview");
  if (!o) return <p className="down" role="alert">The API is unreachable or rejected the token. Check that the api container is healthy.</p>;
  return (
    <>
      <h1>Overview</h1>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.entries<any>(o.markets).map(([m, v]) => (
          <div key={m} className="panel p-4"><div className="flex items-center justify-between"><span className="font-semibold">{m}</span>
            <span className="text-xs flex items-center gap-1.5" style={{ color: v.open ? "var(--up)" : "var(--mute)" }}><span className="dot" style={{ "--c": "currentColor" } as React.CSSProperties} />{v.open ? "Open" : "Closed"}</span></div>
            {v.last_run ? <><div className="text-sm mt-2">{v.last_run.candidates} candidates <span className="mute">of {v.last_run.scanned} scanned</span></div>
              <div className="text-xs mute mt-1" suppressHydrationWarning>Last scan {when(v.last_run.at)}{v.last_run.failed ? <span className="warn"> · {v.last_run.failed} failed</span> : null}</div></> : <div className="text-sm mute mt-2">No scan yet</div>}</div>))}
        <div className="panel p-4"><div className="font-semibold">Active opportunities</div><div className="text-2xl font-semibold mt-1">{o.active_opportunities}</div><div className="text-xs mute mt-1">in the last 24 hours</div></div>
      </div>
      <section><h2 className="mb-2">Highest-ranked candidates</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>Company</th><th className="n">Day</th><th className="n">Quality</th><th className="n">Opportunity</th><th>Class</th></tr></thead><tbody>
          {o.top.map((r: any) => <tr key={r.symbol}><td><Link className="underline font-medium" href={`/company/${r.symbol}`}>{r.name}</Link></td><td className={`n ${tone(r.daily_change_pct)}`}>{pct(r.daily_change_pct)}</td><td className="n">{num(r.quality_score)}</td><td className="n">{num(r.opportunity_score)}</td><td><Badge c={r.classification} /></td></tr>)}
          {!o.top.length && <tr><td colSpan={5} className="mute py-6 text-center">No candidates right now.</td></tr>}</tbody></table></div></section>
      <section><h2 className="mb-2">Data providers</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-sm"><tbody>
          {o.providers.map((p: any) => <tr key={p.provider}><td className="font-medium">{p.provider}</td><td>{p.status === "failing" ? <span className="down">Failing ({p.consecutive_failures} in a row)</span> : p.status === "degraded" ? <span className="warn">Degraded ({p.failures} failed of {p.successes + p.failures} calls)</span> : <span className="up">Healthy</span>}</td><td className="mute" suppressHydrationWarning>Last ok {p.last_success ? when(p.last_success) : "never"}</td><td className="mute whitespace-normal min-w-64">{p.last_error}</td></tr>)}
          {!o.providers.length && <tr><td className="mute py-6 text-center">No provider calls yet.</td></tr>}</tbody></table></div></section>
      <section><h2 className="mb-2">Recent alerts</h2>
        <div className="panel overflow-x-auto"><table className="w-full text-sm"><tbody>
          {o.alerts.map((a: any, i: number) => <tr key={i}><td className="mute" suppressHydrationWarning>{when(a.at)}</td><td>{a.kind}</td><td className="mute">{a.status}</td><td className="whitespace-normal min-w-64">{a.message.split("\n")[0]}</td></tr>)}
          {!o.alerts.length && <tr><td className="mute py-6 text-center">No alerts sent yet.</td></tr>}</tbody></table></div></section>
    </>
  );
}
