import Link from "next/link";
const items = [["/", "Overview"], ["/opportunities", "Opportunities"], ["/watchlist", "Watchlist"], ["/performance", "Performance"], ["/settings", "Settings"]];
export default function Nav() {
  return (
    <nav className="flex gap-4 overflow-x-auto px-4 py-3 border-b" style={{ borderColor: "var(--line)" }}>
      {items.map(([h, l]) => <Link key={h} href={h} className="text-sm whitespace-nowrap hover:underline">{l}</Link>)}
    </nav>
  );
}
