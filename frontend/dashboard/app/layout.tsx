import "./globals.css";
import Nav from "@/components/Nav";
export const metadata = { title: "Opportunity Radar", robots: { index: false, follow: false } };
export default function Root({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1" /></head>
      <body><Nav /><main className="p-4 max-w-6xl mx-auto space-y-6">{children}
        <p className="text-xs mute pb-6">Decision support only. Scores rank research candidates; they are not return forecasts or investment advice.</p></main></body></html>
  );
}
