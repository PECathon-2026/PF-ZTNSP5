import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "KAGE AI · Engineering Guild", template: "%s · KAGE AI" },
  description: "KAGE AI — build in the shadows, prove in the light.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Shippori+Mincho:wght@500;600&display=swap" rel="stylesheet" />
      </head>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <SiteHeader />
        <main id="main-content">{children}</main>
        <footer className="site-footer"><span className="font-display text-lg text-washi">KAGE <span className="text-gold">AI</span></span><span>PECATHON 2026 · Build in the shadows. Prove in the light.</span><a href="#main-content">Back to top ↑</a></footer>
      </body>
    </html>
  );
}
