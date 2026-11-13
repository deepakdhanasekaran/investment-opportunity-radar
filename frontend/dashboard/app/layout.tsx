import "./globals.css";
import localFont from "next/font/local";
import Nav from "@/components/Nav";
const sans = localFont({ src: "./plex-sans.woff2", weight: "100 700", variable: "--font-sans", display: "swap" });
export const metadata = { title: "Opportunity Radar", robots: { index: false, follow: false } };
export default function Root({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={sans.variable}><head><meta name="viewport" content="width=device-width, initial-scale=1" /></head>
      <body><Nav /><main className="px-4 py-6 max-w-6xl mx-auto"><div className="page space-y-6">{children}</div>
        <p className="text-xs mute py-8">Decision support only. Scores rank research candidates; they are not return forecasts or investment advice.</p></main></body></html>
  );
}
