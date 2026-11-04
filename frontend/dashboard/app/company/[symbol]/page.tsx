import { api, num, pct } from "@/lib/api";
import Badge from "@/components/Badge";
import PriceChart from "@/components/PriceChart";

const PCT = /growth|margin|^roe$|^roic$/;  // Yahoo returns these as fractions
const fmt = (k: string, v: any, cur: string) =>
  typeof v !== "number" ? String(v ?? "–")
  : PCT.test(k) ? `${(v * 100).toFixed(1)}%`
  : /_pct$/.test(k) ? `${v.toFixed(1)}%`
  : /cash_flow|revenue$|market_cap|debt$|cash$|^ebitda$/.test(k) ? `${new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(v)} ${cur}`
  : k === "volume_ratio" ? `${v.toFixed(2)}x (pro-rated)`
  : v.toFixed(2);
const J = ({ o, cur = "" }: { o: Record<string, any> | null; cur?: string }) => (
  <table className="text-sm w-full"><tbody>{Object.entries(o ?? {}).map(([k, v]) => <tr key={k}><td className="mute">{k}</td><td>{fmt(k, v, cur)}</td></tr>)}</tbody></table>
);

export default async function Company({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const [c, p] = await Promise.all([api(`/api/companies/${encodeURIComponent(symbol)}`), api(`/api/companies/${encodeURIComponent(symbol)}/prices?days=365`)]);
  if (!c) return <p className="text-red-400">Unknown symbol or API unreachable.</p>;
  const a = c.latest, r = a?.report, fx = r?.facts;
  return (
    <>
      <h1 className="text-xl font-semibold">{c.security.name} <span className="mute text-base">{c.security.symbol} · {c.security.exchange} · {c.security.currency}</span></h1>
      <div className="panel p-4"><PriceChart bars={p?.bars ?? []} /></div>
      {!a ? <p className="mute">No analysis yet. Analyses are created when the scanner flags this stock.</p> : <>
        <div className="panel p-4 space-y-2">
          <div className="flex gap-3 items-center flex-wrap"><Badge c={a.classification} /><span>Quality {num(a.quality_score)} ({Math.round(a.quality_confidence * 100)}% data)</span><span>Opportunity {num(a.opportunity_score)}</span><span>Risk {a.risk_level}</span>{a.incomplete && <span className="text-amber-400">Incomplete data</span>}</div>
          <p className="text-sm">{r.interpretation.decline_explanation}</p><p className="text-sm">{r.interpretation.financial_assessment}</p><p className="text-sm">{r.interpretation.valuation}</p>
          <p className="text-xs mute">Quote {Number(fx.price).toFixed(2)} {fx.currency} at {fx.quote_ts} from {fx.quote_source} · day {pct(fx.daily_change_pct)} · 5d {pct(fx.five_day_change_pct)} · providers: {fx.providers.join(", ")}</p>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="panel p-4"><h2 className="font-semibold mb-2">Why this classification</h2><ul className="text-sm list-disc pl-5">{a.factors.verdict.rules.map((x: string) => <li key={x}>{x}</li>)}</ul>
            <h3 className="font-semibold mt-3 mb-1">Risk factors</h3><ul className="text-sm list-disc pl-5">{a.factors.risk_flags.map((f: any, i: number) => <li key={i}><b>{f.severity}</b> {f.text}</li>)}{!a.factors.risk_flags.length && <li>None identified by the rules</li>}</ul></div>
          <div className="panel p-4"><h2 className="font-semibold mb-2">Uncertainties</h2><ul className="text-sm list-disc pl-5">{r.uncertainties.map((u: string) => <li key={u}>{u}</li>)}{!r.uncertainties.length && <li>None recorded</li>}</ul></div>
          <div className="panel p-4"><h2 className="font-semibold mb-2">Financial metrics (Yahoo)</h2><J o={fx.fundamentals} cur={fx.currency} /></div>
          <div className="panel p-4"><h2 className="font-semibold mb-2">Valuation & technicals</h2><J o={{ ...fx.valuation, sma50: fx.sma50, sma200: fx.sma200, drawdown_20d_pct: fx.drawdown_20d_pct, volatility_ann_pct: fx.volatility_ann_pct, volume_ratio: fx.volume_ratio }} /></div>
        </div>
        <div className="panel p-4"><h2 className="font-semibold mb-2">News (headline sentiment: {c.news[0]?.model ?? "n/a"})</h2><ul className="text-sm space-y-1">{c.news.map((n: any, i: number) => <li key={i}><a className="underline" href={n.url} target="_blank" rel="noreferrer noopener">{n.title}</a> <span className="mute">{n.publisher} · {num(n.sentiment, 2)}</span></li>)}{!c.news.length && <li className="mute">No articles stored.</li>}</ul></div>
      </>}
      <div className="panel p-4 overflow-x-auto"><h2 className="font-semibold mb-2">Historical signals</h2><table className="text-sm w-full"><tbody>
        {c.signals.map((s: any, i: number) => <tr key={i}><td className="mute">{new Date(s.at).toLocaleString()}</td><td>{s.strategy}</td><td>{s.price}</td><td>{pct(s.daily_change_pct)}</td></tr>)}{!c.signals.length && <tr><td className="mute">None.</td></tr>}</tbody></table></div>
    </>
  );
}
