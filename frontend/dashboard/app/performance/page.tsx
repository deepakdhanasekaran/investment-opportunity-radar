import { api, pct, tone, when } from "@/lib/api";

const P = (v: number | null | undefined) => <span className={tone(v)}>{v == null ? "–" : pct(v * 100)}</span>;
const T = ({ head, children }: { head: string[]; children: React.ReactNode }) => (
  <div className="overflow-x-auto -mx-4 px-4"><table className="text-sm w-full"><thead><tr>{head.map((h, i) => <th key={h} className={i ? "n" : "pl-0"}>{h}</th>)}</tr></thead><tbody>{children}</tbody></table></div>
);
const Empty = ({ n, children }: { n: number; children: React.ReactNode }) => <tr><td colSpan={n} className="mute pl-0 py-4">{children}</td></tr>;

export default async function Page() {
  const [p, b] = await Promise.all([api("/api/performance"), api("/api/backtests")]);
  const holds = Object.entries<any>(p?.by_holding ?? {}), open: any[] = p?.open_positions ?? [], strat = Object.entries<number>(p?.by_strategy_20d_mean_excess ?? {});
  return (
    <>
      <h1>Performance</h1>
      <section className="panel p-4 space-y-5">
        <div><h2>Paper trading</h2><p className="text-sm mute mt-1 max-w-[75ch]">Live GREEN opportunities, tracked hypothetically. {p?.note}</p><p className="text-sm mt-2">Tracked GREEN opportunities: <b>{p?.tracked_green ?? 0}</b></p></div>
        <div><h3 className="mb-1">Open positions <span className="mute font-normal">· stake per GREEN: SE 1000 SEK, US 100 USD, IN 10000 INR</span></h3>
          <T head={["Symbol", "Entry", "Now", "P/L", "Day", "Sell at ≥ 20d high", "Sell at ≥ 50d avg", "Stop (8% trail)"]}>
            {open.map((r) => <tr key={r.symbol}><td className="pl-0"><a className="underline font-medium" href={`/company/${r.symbol}`}>{r.symbol}</a></td><td className="n">{r.position.entry.toFixed(2)}</td><td className="n">{r.position.last.toFixed(2)}</td>
              <td className={`n ${tone(r.position.unrealized_pct)}`}>{r.position.unrealized.toFixed(0)} {r.currency} ({pct(r.position.unrealized_pct * 100)})</td><td className="n mute">{r.position.days_held}/60</td>
              <td className="n">{r.position.targets.hi20.toFixed(2)}</td><td className="n">{r.position.targets.ma50.toFixed(2)}</td><td className="n">{r.position.targets.trail8.toFixed(2)}</td></tr>)}
            {!open.length && <Empty n={8}>No open positions.</Empty>}</T></div>
        <div><h3 className="mb-1">Exit rules <span className="mute font-normal">· max hold 60 days</span></h3>
          <T head={["Rule", "Closed", "Open", "Win rate", "Mean return", "Mean excess", "Avg days", "P/L (closed)", "Hit 60d cap"]}>
            {Object.entries<any>(p?.by_exit_rule ?? {}).map(([k, x]) => <tr key={k}><td className="pl-0">{x.label}</td><td className="n">{x.n}</td><td className="n">{x.still_open}</td><td className="n">{x.n ? `${(x.win_rate * 100).toFixed(0)}%` : "–"}</td><td className="n">{P(x.n ? x.mean_return : null)}</td><td className="n">{P(x.n ? x.mean_excess : null)}</td><td className="n">{x.n ? x.mean_days.toFixed(0) : "–"}</td><td className={`n ${tone(x.n ? x.total_pnl : null)}`}>{x.n ? x.total_pnl.toFixed(0) : "–"}</td><td className="n">{x.n ? `${(x.cap_exit_share * 100).toFixed(0)}%` : "–"}</td></tr>)}</T></div>
        <div><h3 className="mb-1">Fixed holding periods</h3>
          <T head={["Days", "n", "Win rate", "Mean return", "Mean excess vs index", "False-positive rate"]}>
            {holds.map(([h, x]) => <tr key={h}><td className="pl-0">{h}</td><td className="n">{x.n}</td><td className="n">{(x.win_rate * 100).toFixed(0)}%</td><td className="n">{P(x.mean_return)}</td><td className="n">{P(x.mean_excess)}</td><td className="n">{(x.false_positive_rate * 100).toFixed(0)}%</td></tr>)}
            {!holds.length && <Empty n={6}>No position has been held for 5 trading days yet.</Empty>}</T></div>
        <div><h3 className="mb-1">Strategy <span className="mute font-normal">· 20-day mean excess return</span></h3>
          {strat.length ? <ul className="text-sm">{strat.map(([k, v]) => <li key={k} className="flex justify-between max-w-sm py-1"><span>{k.replaceAll("_", " ")}</span>{P(v)}</li>)}</ul> : <p className="text-sm mute">Available once a position has been held for 20 trading days.</p>}</div>
      </section>
      <section className="panel p-4 space-y-2"><h2>Historical backtests</h2>
        {(b ?? []).length === 0 && <p className="text-sm mute">None stored. Run: <code>docker compose run --rm scheduler backtest SE</code></p>}
        {(b ?? []).map((r: any, i: number) => <details key={r.id} className="text-sm" open={i === 0}><summary><span className="font-medium">{r.params?.market}</span> <span className="mute" suppressHydrationWarning>· {when(r.at)} · {r.params?.symbols} symbols</span></summary>
          <div className="space-y-4 pb-3">
          {r.result.portfolio && <div><h3 className="mb-1">One account, max {r.params?.slots ?? 10} positions, costs included</h3><p className="mute mb-1">Compare each rule with simply holding the same stocks.</p>
            <T head={["Rule", "Period", "Trades", "Invested", "Return / yr", "Worst drop", "Hold universe / yr", "Its worst drop", "Index / yr"]}>
              {Object.values<any>(r.result.portfolio).flatMap((x: any) => [["All", x.all], ["Out-of-sample", x.out_of_sample]].filter(([, v]: any) => v?.trades).map(([k, v]: any) => <tr key={x.label + k}><td className="pl-0">{x.label}</td><td className="n mute">{k}</td><td className="n">{v.trades}</td><td className="n">{(v.avg_exposure * 100).toFixed(0)}%</td><td className="n">{P(v.strategy.cagr)}</td><td className="n">{P(v.strategy.max_drawdown)}</td><td className="n">{P(v.universe_equal_weight.cagr)}</td><td className="n">{P(v.universe_equal_weight.max_drawdown)}</td><td className="n">{P(v.index_price_only?.cagr)}</td></tr>))}</T></div>}
          {r.result.exit_rules && <div><h3 className="mb-1">Per trade, unlimited capital</h3>
            <T head={["Exit rule", "Trades", "Win rate", "Mean return", "vs index", "vs universe", "Avg days", "Hit 60d cap", "OOS mean return"]}>
              {Object.values<any>(r.result.exit_rules).map((x: any) => <tr key={x.label}><td className="pl-0">{x.label}</td><td className="n">{x.all.signals}</td><td className="n">{x.all.signals ? `${(x.all.win_rate * 100).toFixed(0)}%` : "–"}</td><td className="n">{P(x.all.mean_return)}</td><td className="n">{P(x.all.mean_excess_vs_benchmark)}</td><td className="n">{P(x.all.mean_excess_vs_universe)}</td><td className="n">{x.all.holding_days ?? "–"}</td><td className="n">{x.all.signals ? `${(x.all.cap_exit_share * 100).toFixed(0)}%` : "–"}</td><td className="n">{P(x.out_of_sample.mean_return)}</td></tr>)}</T></div>}
          <details><summary className="mute">Method caveats ({(r.result.warnings ?? []).length})</summary><ul className="list-disc pl-5 warn space-y-1 max-w-[75ch]">{(r.result.warnings ?? []).map((w: string) => <li key={w}>{w}</li>)}</ul></details>
          <details><summary className="mute">Raw fixed-hold results</summary><pre className="overflow-x-auto text-xs">{JSON.stringify({ in_sample: r.result.in_sample, out_of_sample: r.result.out_of_sample }, null, 1)}</pre></details>
          </div></details>)}</section>
    </>
  );
}
