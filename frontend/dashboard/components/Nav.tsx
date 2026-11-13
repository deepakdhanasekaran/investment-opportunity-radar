"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
const items = [["/", "Overview"], ["/opportunities", "Opportunities"], ["/watchlist", "Watchlist"], ["/performance", "Performance"], ["/settings", "Settings"]];
export default function Nav() {
  const path = usePathname();
  if (path === "/login") return null;
  const on = (h: string) => (h === "/" ? path === "/" : path.startsWith(h)) || (h === "/opportunities" && path.startsWith("/company"));
  return (
    <header className="sticky top-0 z-10 border-b backdrop-blur-md" style={{ borderColor: "var(--line)", background: "color-mix(in oklab, var(--bg) 82%, transparent)" }}>
      <nav className="max-w-6xl mx-auto flex items-center gap-1 overflow-x-auto px-4" aria-label="Main">
        <Link href="/" className="flex items-center gap-2 pr-4 py-3 font-semibold whitespace-nowrap" aria-label="Opportunity Radar home">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="var(--accent)" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
            <circle cx="9" cy="9" r="7.5" opacity=".45" /><circle cx="9" cy="9" r="3.5" opacity=".7" /><path d="M9 9 14.3 3.7" /><circle cx="9" cy="9" r=".9" fill="var(--accent)" /></svg>
          <span className="hidden sm:inline">Radar</span></Link>
        {items.map(([h, l]) => (
          <Link key={h} href={h} aria-current={on(h) ? "page" : undefined}
            className="relative px-3 py-3 text-sm whitespace-nowrap transition-colors hover:text-[var(--fg)]" style={{ color: on(h) ? "var(--fg)" : "var(--mute)" }}>
            {l}<span className="absolute inset-x-3 -bottom-px h-0.5 rounded-full transition-transform duration-300 origin-center" style={{ background: "var(--accent)", transform: on(h) ? "scaleX(1)" : "scaleX(0)", transitionTimingFunction: "var(--ease)" }} /></Link>))}
      </nav>
    </header>
  );
}
