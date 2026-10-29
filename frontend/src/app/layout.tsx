import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteHeader } from "@/components/shell/site-header";
import { MissionSessionProvider } from "@/components/shell/mission-context";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "KAGE AI · Autonomous Engineering Guild", template: "%s · KAGE AI" },
  description: "KAGE AI — build in the shadows, prove in the light.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Cinzel+Decorative:wght@400;700&family=Cinzel:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Shippori+Mincho:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <MissionSessionProvider>
          <div className="app-shell">
            <SiteHeader />
            <main id="main-content" className="app-main">
              {children}
            </main>
            <footer className="site-footer">
              <span className="wordmark">KAGE <span>AI</span></span>
              <span>Build in the shadows. Prove in the light.</span>
              <span>PECATHON 2026 · PS-001</span>
            </footer>
          </div>
        </MissionSessionProvider>
      </body>
    </html>
  );
}
