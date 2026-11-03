import { CLS } from "@/lib/api";
export default function Badge({ c }: { c: string }) {
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${CLS[c] ?? ""}`}>{c}</span>;
}
