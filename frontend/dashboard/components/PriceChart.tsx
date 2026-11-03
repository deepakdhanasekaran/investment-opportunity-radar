export default function PriceChart({ bars }: { bars: { t: string; c: number }[] }) {
  if (bars.length < 2) return <p className="mute text-sm">No price data.</p>;
  const W = 800, H = 220, min = Math.min(...bars.map((b) => b.c)), max = Math.max(...bars.map((b) => b.c));
  const pts = bars.map((b, i) => `${(i / (bars.length - 1)) * W},${H - ((b.c - min) / (max - min || 1)) * (H - 10) - 5}`).join(" ");
  return (
    <figure>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Price history"><polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={pts} /></svg>
      <figcaption className="text-xs mute">{bars[0].t} to {bars.at(-1)!.t} · low {min.toFixed(2)} · high {max.toFixed(2)} · dividend/split-adjusted close (Yahoo)</figcaption>
    </figure>
  );
}
