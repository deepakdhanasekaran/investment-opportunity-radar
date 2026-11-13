import { CLS } from "@/lib/api";
export default function Badge({ c }: { c: string }) {
  return <span className="badge" style={{ "--c": CLS[c] ?? "var(--mute)" } as React.CSSProperties}>{c}</span>;
}
