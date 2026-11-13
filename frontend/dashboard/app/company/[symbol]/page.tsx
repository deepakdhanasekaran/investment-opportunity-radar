import { api, num, pct, tone, when } from "@/lib/api";
import Badge from "@/components/Badge";
import PriceChart from "@/components/PriceChart";

const PCT = /growth|margin|^roe$|^roic$/;  // Yahoo returns these as fractions
const UP: Record<string, string> = { pe: "P/E", forward_pe: "Forward P/E", pb: "P/B", ev_ebitda: "EV/EBITDA", roe: "ROE", roic: "ROIC", sma50: "50-day average", sma200: "200-day average",
  hist_pe_median: "Own median P/E", pe_vs_hist: "P/E vs own median", drawdown_20d_pct: "Off 20-day high", volatility_ann_pct: "Volatility (annualised)", volume_ratio: "Volume vs 20-day average" };
const label = (k: string) => UP[k] ?? (k[0].toUpperCase() + k.slice(1)).replaceAll("_", " ");
const fmt = (k: string, v: any, cur: string) =>
  typeof v !== "number" ? String(v ?? "–")
  : PCT.test(k) ? `${(v * 100).toFixed(1)}%`
  : /_pct$/.test(k) ? `${v.toFixed(1)}%`
  : /cash_flow|revenue$|market_cap|debt$|cash$|^ebitda$/.test(k) ? `${new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 2 }).format(v)} ${cur}`
  : k === "volume_ratio" ? `${v.toFixed(2)}x (pro-rated)`
  : v.toFixed(2);
const J = ({ o, cur = "" }: { o: Record<string, any> | null; cur?: string }) => (
  <table className="text-sm w-full"><tbody>{Object.entries(o ?? {}).map(([k, v]) => <tr key={k}><td className="mute pl-0">{label(k)}</td><td className="n pr-0">{fmt(k, v, cur)}</td></tr>)}</tbody></table>
);
const SEV: Record<string, string> = { CRITICAL: "down", REVIEW: "warn", INFO: "mute" };
const Stat = ({ k, children }: { k: string; children: React.ReactNode }) => <div><div className="text-xs mute">{k}</div><div className="font-semibold">{children}</div></div>;
const Levels = ({ title, xs, fx }: { title: string; xs: any[]; fx: any }) => (
  <div><h3 className="mute font-normal mb-1">{title}</h3>{xs.map((l: any) => <div key={l.label} className="flex justify-between gap-4 py-1"><span>{l.label}</span><span>{Number(l.price).toFixed(2)} {fx.currency} <span className="mute">({pct((l.price / fx.price - 1) * 100)})</span></span></div>)}{!xs.length && <div className="mute">None</div>}</div>
);

export default async function Company({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const [c, p] = await Promise.all([api(`/api/companies/${encodeURIComponent(symbol)}`), api(`/api/companies/${encodeURIComponent(symbol)}/prices?days=365`)]);
  if (!c) return <p className="down" role="alert">Unknown symbol, or the API is unreachable.</p>;
  const a = c.latest, r = a?.report, fx = r?.facts;
  return (
    <>
      <div><h1>{c.security.name}</h1><p className="mute text-sm mt-1">{c.security.symbol} · {c.security.exchange} · {c.security.currency}</p></div>
      <div className="panel p-4"><PriceChart bars={p?.bars ?? []} /></div>
      {!a ? <p className="mute">No analysis yet. Analyses are created when the scanner flags this stock.</p> : <>
        <div className="panel p-4 space-y-3">
          <div className="flex gap-x-8 gap-y-3 items-center flex-wrap"><Badge c={a.classification} />
            <Stat k="Quality">{num(a.quality_score)} <span className="mute font-normal text-xs">{Math.round(a.quality_confidence * 100)}% data</span></Stat>
            <Stat k="Opportunity">{num(a.opportunity_score)}</Stat><Stat k="Risk">{a.risk_level[0] + a.risk_level.slice(1).toLowerCase()}</Stat>
            <Stat k="Day"><span className={tone(fx.daily_change_pct)}>{pct(fx.daily_change_pct)}</span></Stat><Stat k="5 days"><span className={tone(fx.five_day_change_pct)}>{pct(fx.five_day_change_pct)}</span></Stat>
            {a.incomplete && <span className="warn text-sm">Incomplete data</span>}</div>
          <div className="text-sm space-y-1 max-w-[75ch]"><p>{r.interpretation.decline_explanation}</p><p>{r.interpretation.financial_assessment}</p><p>{r.interpretation.valuation}</p></div>
          <p className="text-xs mute" suppressHydrationWarning>Quote {Number(fx.price).toFixed(2)} {fx.currency} at {when(fx.quote_ts)} from {fx.quote_source} · providers: {fx.providers.join(", ")}</p>
        </div>
        <div className="grid md:grid-cols-2 gap-4">
          <div className="panel p-4"><h2 className="mb-2">Why this classification</h2><ul className="text-sm list-disc pl-5 space-y-1">{a.factors.verdict.rules.map((x: string) => <li key={x}>{x}</li>)}</ul>
            <h3 className="mt-4 mb-1">Risk factors</h3><ul className="text-sm space-y-1">{a.factors.risk_flags.map((f: any, i: number) => <li key={i}><span className={`${SEV[f.severity] ?? ""} text-xs font-semibold mr-1.5`}>{f.severity}</span>{f.text}</li>)}{!a.factors.risk_flags.length && <li className="mute">None identified by the rules</li>}</ul></div>
          <div className="panel p-4"><h2 className="mb-2">Uncertainties</h2><ul className="text-sm list-disc pl-5 space-y-1">{r.uncertainties.map((u: string) => <li key={u}>{u}</li>)}{!r.uncertainties.length && <li className="mute">None recorded</li>}</ul></div>
          <div className="panel p-4"><h2 className="mb-1">Financial metrics (Yahoo)</h2><J o={fx.fundamentals} cur={fx.currency} /></div>
          <div className="panel p-4"><h2 className="mb-1">Valuation and technicals</h2><J o={{ ...fx.valuation, sma50: fx.sma50, sma200: fx.sma200, drawdown_20d_pct: fx.drawdown_20d_pct, volatility_ann_pct: fx.volatility_ann_pct, volume_ratio: fx.volume_ratio }} /></div>
        </div>
        {fx.levels && <div className="panel p-4"><h2>Reference levels</h2><p className="mute text-xs mb-3">Not targets, not a recommendation: computed from price history only.</p>
          <div className="grid md:grid-cols-2 gap-x-8 gap-y-4 text-sm"><Levels title="Above current price" xs={fx.levels.upside} fx={fx} /><Levels title="Below current price" xs={fx.levels.downside} fx={fx} /></div>
          {fx.next_earnings && <p className="text-xs mute mt-3">Next earnings (Yahoo calendar): {fx.next_earnings}</p>}</div>}
        <div className="panel p-4"><h2 className="mb-2">News <span className="mute text-xs font-normal">headline sentiment: {c.news[0]?.model ?? "n/a"}</span></h2><ul className="text-sm space-y-2">{c.news.map((n: any, i: number) => <li key={i}><a className="underline" href={n.url} target="_blank" rel="noreferrer noopener">{n.title}</a> <span className="mute text-xs whitespace-nowrap">{n.publisher} · <span className={tone(n.sentiment)}>{num(n.sentiment, 2)}</span></span></li>)}{!c.news.length && <li className="mute">No articles stored.</li>}</ul></div>
      </>}
      <div className="panel p-4"><h2 className="mb-1">Historical signals</h2><div className="overflow-x-auto"><table className="text-sm w-full"><tbody>
        {c.signals.map((s: any, i: number) => <tr key={i}><td className="mute pl-0" suppressHydrationWarning>{when(s.at)}</td><td>{s.strategy.replaceAll("_", " ")}</td><td className="n">{Number(s.price).toFixed(2)}</td><td className={`n pr-0 ${tone(s.daily_change_pct)}`}>{pct(s.daily_change_pct)}</td></tr>)}{!c.signals.length && <tr><td className="mute pl-0">None.</td></tr>}</tbody></table></div></div>
    </>
  );
}
