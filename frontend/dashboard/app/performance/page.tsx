import { api, pct } from "@/lib/api";
export default async function Page() {
  const [p, b] = await Promise.all([api("/api/performance"), api("/api/backtests")]);
  return (
    <>
      <h1 className="text-xl font-semibold">Performance</h1>
      <section className="panel p-4 space-y-2"><h2 className="font-semibold">Paper trading (live GREEN opportunities, hypothetical)</h2>
        <p className="text-sm mute">{p?.note}</p><p className="text-sm">Tracked GREEN opportunities: {p?.tracked_green ?? 0}</p>
        <table className="text-sm w-full"><thead><tr className="mute"><th>Days</th><th>n</th><th>Win rate</th><th>Mean return</th><th>Mean excess vs index</th><th>False-positive rate</th></tr></thead><tbody>
          {Object.entries<any>(p?.by_holding ?? {}).map(([h, x]) => <tr key={h}><td>{h}</td><td>{x.n}</td><td>{pct(x.win_rate * 100)}</td><td>{pct(x.mean_return * 100)}</td><td>{pct(x.mean_excess * 100)}</td><td>{pct(x.false_positive_rate * 100)}</td></tr>)}</tbody></table>
        <h3 className="font-semibold pt-2">Open positions (stake per GREEN: SE 1000 SEK, US 100 USD, IN 10000 INR)</h3>
        {(p?.open_positions ?? []).length === 0 ? <p className="text-sm mute">No open positions.</p> :
        <table className="text-sm w-full"><thead><tr className="mute"><th>Symbol</th><th>Entry</th><th>Now</th><th>P/L</th><th>Day</th><th>Sell at ≥ 20d high</th><th>Sell at ≥ 50d avg</th><th>Stop (8% trail)</th></tr></thead><tbody>
          {p.open_positions.map((r: any) => <tr key={r.symbol}><td>{r.symbol}</td><td>{r.position.entry.toFixed(2)}</td><td>{r.position.last.toFixed(2)}</td>
            <td>{r.position.unrealized.toFixed(0)} {r.currency} ({pct(r.position.unrealized_pct * 100)})</td><td>{r.position.days_held}/60</td>
            <td>{r.position.targets.hi20.toFixed(2)}</td><td>{r.position.targets.ma50.toFixed(2)}</td><td>{r.position.targets.trail8.toFixed(2)}</td></tr>)}</tbody></table>}
        <h3 className="font-semibold pt-2">Exit rules (max hold 60 days; vs fixed holds above)</h3>
        <table className="text-sm w-full"><thead><tr className="mute"><th>Rule</th><th>Closed</th><th>Open</th><th>Win rate</th><th>Mean return</th><th>Mean excess</th><th>Avg days</th><th>P/L (closed)</th><th>Hit 60d cap</th></tr></thead><tbody>
          {Object.entries<any>(p?.by_exit_rule ?? {}).map(([k, x]) => <tr key={k}><td>{x.label}</td><td>{x.n}</td><td>{x.still_open}</td><td>{x.n ? pct(x.win_rate * 100) : "–"}</td><td>{x.n ? pct(x.mean_return * 100) : "–"}</td><td>{x.n ? pct(x.mean_excess * 100) : "–"}</td><td>{x.n ? x.mean_days.toFixed(0) : "–"}</td><td>{x.n ? x.total_pnl.toFixed(0) : "–"}</td><td>{x.n ? pct(x.cap_exit_share * 100) : "–"}</td></tr>)}</tbody></table>
        <h3 className="font-semibold pt-2">Strategy (20-day mean excess return)</h3>
        <ul className="text-sm">{Object.entries<number>(p?.by_strategy_20d_mean_excess ?? {}).map(([k, v]) => <li key={k}>{k}: {pct(v * 100)}</li>)}</ul></section>
      <section className="panel p-4 space-y-2"><h2 className="font-semibold">Historical backtests</h2>
        {(b ?? []).length === 0 && <p className="text-sm mute">None stored. Run: <code>docker compose run --rm scheduler backtest SE</code></p>}
        {(b ?? []).map((r: any) => <details key={r.id} className="text-sm"><summary>{r.at} · {r.kind} · {r.params?.market}</summary>
          <ul className="list-disc pl-5 text-amber-400">{(r.result.warnings ?? []).map((w: string) => <li key={w}>{w}</li>)}</ul>
          {r.result.exit_rules && <table className="text-sm w-full my-2"><thead><tr className="mute"><th>Exit rule</th><th>Trades</th><th>Win rate</th><th>Mean return</th><th>vs index</th><th>Avg days</th><th>Hit 60d cap</th><th>OOS mean return</th></tr></thead><tbody>
            {Object.values<any>(r.result.exit_rules).map((x: any) => <tr key={x.label}><td>{x.label}</td><td>{x.all.signals}</td><td>{x.all.signals ? pct(x.all.win_rate * 100) : "–"}</td><td>{x.all.signals ? pct(x.all.mean_return * 100) : "–"}</td><td>{x.all.mean_excess_vs_benchmark != null ? pct(x.all.mean_excess_vs_benchmark * 100) : "–"}</td><td>{x.all.holding_days ?? "–"}</td><td>{x.all.signals ? pct(x.all.cap_exit_share * 100) : "–"}</td><td>{x.out_of_sample.signals ? pct(x.out_of_sample.mean_return * 100) : "–"}</td></tr>)}</tbody></table>}
          <pre className="overflow-x-auto text-xs">{JSON.stringify({ in_sample: r.result.in_sample, out_of_sample: r.result.out_of_sample }, null, 1)}</pre></details>)}</section>
    </>
  );
}
