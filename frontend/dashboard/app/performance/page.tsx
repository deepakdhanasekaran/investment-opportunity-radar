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
        <h3 className="font-semibold pt-2">Strategy (20-day mean excess return)</h3>
        <ul className="text-sm">{Object.entries<number>(p?.by_strategy_20d_mean_excess ?? {}).map(([k, v]) => <li key={k}>{k}: {pct(v * 100)}</li>)}</ul></section>
      <section className="panel p-4 space-y-2"><h2 className="font-semibold">Historical backtests</h2>
        {(b ?? []).length === 0 && <p className="text-sm mute">None stored. Run: <code>docker compose run --rm scheduler backtest SE</code></p>}
        {(b ?? []).map((r: any) => <details key={r.id} className="text-sm"><summary>{r.at} · {r.kind} · {r.params?.market}</summary>
          <ul className="list-disc pl-5 text-amber-400">{(r.result.warnings ?? []).map((w: string) => <li key={w}>{w}</li>)}</ul>
          <pre className="overflow-x-auto text-xs">{JSON.stringify({ in_sample: r.result.in_sample, out_of_sample: r.result.out_of_sample }, null, 1)}</pre></details>)}</section>
    </>
  );
}
