import { api } from "@/lib/api";
import WatchlistClient from "@/components/WatchlistClient";
export default async function Page() {
  const w = await api("/api/watchlist");
  return <><h1 className="text-xl font-semibold">Watchlist</h1><WatchlistClient initial={w ?? []} /></>;
}
