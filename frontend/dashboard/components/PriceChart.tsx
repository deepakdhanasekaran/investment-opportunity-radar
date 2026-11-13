"use client";
import { useState } from "react";
export default function PriceChart({ bars }: { bars: { t: string; c: number }[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (bars.length < 2) return <p className="mute text-sm">No price data.</p>;
  const W = 800, H = 240, n = bars.length, min = Math.min(...bars.map((b) => b.c)), max = Math.max(...bars.map((b) => b.c));
  const x = (i: number) => (i / (n - 1)) * W, y = (c: number) => H - 8 - ((c - min) / (max - min || 1)) * (H - 16);
  const line = bars.map((b, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(b.c).toFixed(1)}`).join("");
  const i = hover ?? n - 1, b = bars[i], chg = (b.c / bars[0].c - 1) * 100, up = bars[n - 1].c >= bars[0].c;
  const move = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    setHover(Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width) * (n - 1)))));
  };
  return (
    <figure>
      <div className="flex items-baseline gap-3 mb-2" aria-live="off">
        <span className="text-2xl font-semibold">{b.c.toFixed(2)}</span>
        <span className={`text-sm ${chg >= 0 ? "up" : "down"}`}>{chg >= 0 ? "+" : ""}{chg.toFixed(1)}% since {bars[0].t}</span>
        <span className="text-sm mute ml-auto">{b.t}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto block cursor-crosshair" style={{ color: up ? "var(--up)" : "var(--down)", touchAction: "pan-y" }}
        role="img" aria-label={`Price history, ${bars[0].t} to ${bars[n - 1].t}`} onPointerMove={move} onPointerDown={move} onPointerLeave={() => setHover(null)}>
        <defs><linearGradient id="pc-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="currentColor" stopOpacity=".22" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></linearGradient></defs>
        {[0.25, 0.5, 0.75].map((f) => <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="var(--line)" strokeWidth="1" vectorEffect="non-scaling-stroke" />)}
        <path d={`${line}L${W},${H}L0,${H}Z`} fill="url(#pc-fill)" />
        <path d={line} fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
        {hover != null && <><line x1={x(i)} x2={x(i)} y1="0" y2={H} stroke="var(--mute)" strokeWidth="1" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
          <circle cx={x(i)} cy={y(b.c)} r="4.5" fill="currentColor" stroke="var(--panel)" strokeWidth="2" /></>}
      </svg>
      <figcaption className="text-xs mute mt-2">Low {min.toFixed(2)} · high {max.toFixed(2)} · dividend/split-adjusted close (Yahoo)</figcaption>
    </figure>
  );
}
