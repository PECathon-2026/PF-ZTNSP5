import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "KAGE AI — The Engineering Dojo", description: "Four agents. One code change. Your approval. An evidence-first developer workspace." };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body><a href="#main" className="skip-link">Skip to content</a>{children}</body></html>;
}
