"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { HealthStatus } from "./health-status";

const routes = [
  { href: "/", name: "Sanctuary" },
  { href: "/setup", name: "New mission" },
  { href: "/dojo", name: "Dojo" },
];

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className={`site-header ${pathname === "/" ? "site-header--landing" : ""}`}>
      <Link href="/" className="site-brand" aria-label="KAGE AI — home">
        <span className="brand-seal" aria-hidden="true">K</span>
        <span>KAGE AI<small>THE ENGINEERING GUILD</small></span>
      </Link>
      <nav className="site-nav" aria-label="Main navigation">
        {routes.map(({ href, name }) => <Link key={href} href={href} aria-current={pathname === href ? "page" : undefined}>{name}</Link>)}
      </nav>
      <div className="site-actions"><HealthStatus /><Link href="/dojo" className="site-action-link">Open dojo <span aria-hidden="true">↗</span></Link></div>
    </header>
  );
}
