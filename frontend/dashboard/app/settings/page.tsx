import { api } from "@/lib/api";
import SettingsForm from "@/components/SettingsForm";
export default async function Page() {
  const s = await api("/api/settings");
  return <><h1 className="text-xl font-semibold">Scanner settings</h1><p className="text-sm mute">Secrets (Telegram, tokens) are environment variables on the server and are intentionally not editable here.</p>{s ? <SettingsForm initial={s} /> : <p className="text-red-400">API unreachable.</p>}</>;
}
