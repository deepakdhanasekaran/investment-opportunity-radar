"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import Badge from "./Badge";

export type Row = { symbol: string; name: string; exchange: string; currency: string; price: number; daily_change_pct: number; five_day_change_pct: number | null;
  quality_score: number | null; quality_confidence: number; opportunity_score: number | null; risk_level: string; classification: string; incomplete: boolean; analyzed_at: string };
const cols: [keyof Row, string][] = [["name", "Company"], ["symbol", "Ticker"], ["exchange", "Exchange"], ["currency", "Cur"], ["price", "Price"], ["daily_change_pct", "Day"], ["five_day_change_pct", "Week"],
  ["quality_score", "Quality"], ["opportunity_score", "Opportunity"], ["risk_level", "Risk"], ["classification", "Class"], ["analyzed_at", "Analysed"]];
const f = (v: number | null, d = 1, s = "") => (v == null ? "–" : `${v.toFixed(d)}${s}`);

export default function OppTable({ rows }: { rows: Row[] }) {
  const [key, setKey] = useState<keyof Row>("opportunity_score");
  const [dir, setDir] = useState(-1);
  const [cls, setCls] = useState("ALL");
  const sorted = useMemo(() => rows.filter((r) => cls === "ALL" || r.classification === cls).sort((a, b) => {
    const x = a[key], y = b[key];
    if (x == null) return 1; if (y == null) return -1;
    return (x > y ? 1 : x < y ? -1 : 0) * dir;
  }), [rows, key, dir, cls]);
  return (
    <div className="space-y-3">
      <select value={cls} onChange={(e) => setCls(e.target.value)}>{["ALL", "GREEN", "YELLOW", "RED"].map((c) => <option key={c}>{c}</option>)}</select>
      <div className="panel overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr>{cols.map(([k, l]) => <th key={k} className="cursor-pointer mute" onClick={() => { setDir(k === key ? -dir : -1); setKey(k); }}>{l}{k === key ? (dir < 0 ? " ▼" : " ▲") : ""}</th>)}</tr></thead>
          <tbody>{sorted.map((r) => (
            <tr key={r.symbol}>
              <td><Link className="underline" href={`/company/${r.symbol}`}>{r.name}</Link></td><td>{r.symbol}</td><td>{r.exchange}</td><td>{r.currency}</td>
              <td>{f(r.price, 2)}</td><td className={r.daily_change_pct < 0 ? "text-red-400" : "text-emerald-400"}>{f(r.daily_change_pct, 1, "%")}</td><td>{f(r.five_day_change_pct, 1, "%")}</td>
              <td>{f(r.quality_score, 0)} <span className="mute text-xs">({Math.round(r.quality_confidence * 100)}%)</span></td><td>{f(r.opportunity_score, 0)}</td>
              <td>{r.risk_level}</td><td><Badge c={r.classification} />{r.incomplete ? <span title="Incomplete data" className="ml-1">⚠</span> : null}</td><td className="mute">{new Date(r.analyzed_at).toLocaleString()}</td>
            </tr>))}
            {!sorted.length && <tr><td colSpan={cols.length} className="mute">No analysed candidates yet.</td></tr>}</tbody>
        </table>
      </div>
    </div>
  );
}
