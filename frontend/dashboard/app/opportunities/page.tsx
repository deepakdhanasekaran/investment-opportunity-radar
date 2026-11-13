import { api } from "@/lib/api";
import OppTable from "@/components/OppTable";
export default async function Page() {
  const rows = await api("/api/opportunities?days=14");
  return <><div><h1>Opportunities</h1><p className="text-sm mute mt-1">Candidates analysed in the last 14 days.</p></div>{rows ? <OppTable rows={rows} /> : <p className="down" role="alert">The API is unreachable. Check that the api container is healthy.</p>}</>;
}
