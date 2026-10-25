import type { Metadata } from "next";
import { IBM_Plex_Mono, Instrument_Sans } from "next/font/google";
import "./globals.css";

// Humanist grotesk for text (headlines at 400/500, never bold) and a mono for every number, eyebrow and column head.
const sans = Instrument_Sans({ variable: "--font-instrument-sans", subsets: ["latin"], weight: ["400", "500", "600"] });
const mono = IBM_Plex_Mono({ variable: "--font-plex-mono", subsets: ["latin"], weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "Subak",
  description:
    "Daily AI spend, projections and allocations by team, with an assistant that proposes reallocations and leaves a receipt.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`dark ${sans.variable} ${mono.variable} h-full antialiased`} style={{ colorScheme: "dark" }}>
      <body className="min-h-full flex flex-col bg-background text-foreground">{children}</body>
    </html>
  );
}
