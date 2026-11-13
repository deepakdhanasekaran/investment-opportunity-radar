import { api } from "@/lib/api";
import SettingsForm from "@/components/SettingsForm";
export default async function Page() {
  const s = await api("/api/settings");
  return <><div><h1>Scanner settings</h1><p className="text-sm mute mt-1 max-w-[75ch]">Secrets (Telegram, tokens) are environment variables on the server and are intentionally not editable here.</p></div>{s ? <SettingsForm initial={s} /> : <p className="down" role="alert">The API is unreachable. Check that the api container is healthy.</p>}</>;
}
