"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { pct, tone, when } from "@/lib/api";
import Badge from "./Badge";

export type Row = { symbol: string; name: string; exchange: string; currency: string; price: number; daily_change_pct: number; five_day_change_pct: number | null;
  quality_score: number | null; quality_confidence: number; opportunity_score: number | null; risk_level: string; classification: string; incomplete: boolean; analyzed_at: string };
const cols: [keyof Row, string, boolean?][] = [["name", "Company"], ["symbol", "Ticker"], ["exchange", "Exchange"], ["price", "Price", true], ["daily_change_pct", "Day", true], ["five_day_change_pct", "Week", true],
  ["quality_score", "Quality", true], ["opportunity_score", "Opportunity", true], ["risk_level", "Risk"], ["classification", "Class"], ["analyzed_at", "Analysed"]];
const f = (v: number | null, d = 1) => (v == null ? "–" : v.toFixed(d));

export default function OppTable({ rows }: { rows: Row[] }) {
  const [key, setKey] = useState<keyof Row>("opportunity_score");
  const [dir, setDir] = useState(-1);
  const [cls, setCls] = useState("ALL");
  const [ex, setEx] = useState("ALL");
  const exchanges = useMemo(() => ["ALL", ...Array.from(new Set(rows.map((r) => r.exchange))).sort()], [rows]);
  const sorted = useMemo(() => rows.filter((r) => (cls === "ALL" || r.classification === cls) && (ex === "ALL" || r.exchange === ex)).sort((a, b) => {
    const x = a[key], y = b[key];
    if (x == null) return 1; if (y == null) return -1;
    return (x > y ? 1 : x < y ? -1 : 0) * dir;
  }), [rows, key, dir, cls, ex]);
  return (
    <div className="space-y-3">
      <div className="flex gap-x-4 gap-y-2 items-center text-sm flex-wrap">
        <div className="seg" role="group" aria-label="Filter by class">{["ALL", "GREEN", "YELLOW", "RED"].map((c) => <button key={c} aria-pressed={cls === c} onClick={() => setCls(c)}>{c === "ALL" ? "All" : c[0] + c.slice(1).toLowerCase()}</button>)}</div>
        <label className="mute flex items-center gap-2">Exchange <select value={ex} onChange={(e) => setEx(e.target.value)} style={{ color: "var(--fg)" }}>{exchanges.map((c) => <option key={c} value={c}>{c === "ALL" ? "All" : c}</option>)}</select></label>
        <span className="mute ml-auto">{sorted.length} of {rows.length}</span>
      </div>
      <div className="panel overflow-x-auto">
        <table className="w-full text-sm dense">
          <thead><tr>{cols.map(([k, l, n]) => <th key={k} className={n ? "n" : ""} aria-sort={k === key ? (dir < 0 ? "descending" : "ascending") : undefined}>
            <button className="ghost inline-flex items-center gap-1" style={{ color: k === key ? "var(--fg)" : undefined }} onClick={() => { setDir(k === key ? -dir : -1); setKey(k); }}>{l}
              <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true" style={{ opacity: k === key ? 1 : 0, transform: dir < 0 ? "none" : "rotate(180deg)", transition: "transform .25s var(--ease), opacity .15s" }}><path d="M1 2.5 4 5.5 7 2.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg></button></th>)}</tr></thead>
          <tbody>{sorted.map((r) => (
            <tr key={r.symbol}>
              <td className="max-w-48 truncate"><Link className="underline font-medium" href={`/company/${r.symbol}`}>{r.name}</Link></td><td className="mute">{r.symbol}</td><td className="mute">{r.exchange}</td>
              <td className="n">{f(r.price, 2)} <span className="mute text-xs">{r.currency}</span></td><td className={`n ${tone(r.daily_change_pct)}`}>{pct(r.daily_change_pct)}</td><td className={`n ${tone(r.five_day_change_pct)}`}>{pct(r.five_day_change_pct)}</td>
              <td className="n">{f(r.quality_score, 0)} <span className="mute text-xs" title="Share of quality metrics that had data">{Math.round(r.quality_confidence * 100)}%</span></td><td className="n">{f(r.opportunity_score, 0)}</td>
              <td className={r.risk_level === "CRITICAL" ? "down" : r.risk_level === "HIGH" ? "warn" : "mute"}>{r.risk_level[0] + r.risk_level.slice(1).toLowerCase()}</td>
              <td><span className="inline-flex items-center gap-1.5"><Badge c={r.classification} />{r.incomplete ? <svg width="14" height="14" viewBox="0 0 16 16" className="warn" role="img" aria-label="Incomplete data"><title>Incomplete data</title><path d="M8 2 14.5 13.5h-13Z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /><path d="M8 6.5v3.2M8 11.6v.1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg> : null}</span></td>
              <td className="mute" suppressHydrationWarning>{when(r.analyzed_at)}</td>
            </tr>))}
            {!sorted.length && <tr><td colSpan={cols.length} className="mute py-8 text-center">{rows.length ? "No candidates match these filters." : "No analysed candidates yet. They appear after the scanner flags a stock."}</td></tr>}</tbody>
        </table>
      </div>
    </div>
  );
}
