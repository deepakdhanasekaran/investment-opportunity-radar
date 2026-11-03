import { api } from "@/lib/api";
import OppTable from "@/components/OppTable";
export default async function Page() {
  const rows = await api("/api/opportunities?days=14");
  return <><h1 className="text-xl font-semibold">Opportunities</h1>{rows ? <OppTable rows={rows} /> : <p className="text-red-400">API unreachable.</p>}</>;
}
