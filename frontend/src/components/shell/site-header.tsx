"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BrandSeal } from "./brand-seal";
import { ConnectionStatus } from "./connection-status";
import { useMissionSession } from "./mission-context";

const primaryRoutes = [
  { href: "/missions", name: "Missions" },
  { href: "/setup", name: "New mission" },
];

export function SiteHeader() {
  const pathname = usePathname();
  const { brief } = useMissionSession();
  const missionRoutes = brief
    ? [
        { href: `/missions/${brief.id}`, name: "Command" },
        { href: `/missions/${brief.id}/forge`, name: "Forge" },
        { href: `/missions/${brief.id}/evidence`, name: "Evidence" },
      ]
    : [];

  function isCurrent(href: string): boolean {
    if (href === "/missions") return pathname === "/missions";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  return (
    <header className="site-header">
      <Link href="/" className="site-brand" aria-label="KAGE AI — mission entrance">
        <BrandSeal />
        <span className="brand-wordmark">
          <strong>
            KAGE <span>AI</span>
          </strong>
          <small>AUTONOMOUS ENGINEERING GUILD</small>
        </span>
      </Link>

      <nav className="site-nav" aria-label="Primary navigation">
        {primaryRoutes.map((route) => (
          <Link key={route.href} href={route.href} aria-current={isCurrent(route.href) ? "page" : undefined}>
            {route.name}
          </Link>
        ))}

        {missionRoutes.length > 0 && (
          <>
            <span className="nav-divider" aria-hidden="true" />
            <span className="nav-context mono" title={brief?.request}>
              {brief?.id}
            </span>
            {missionRoutes.map((route) => (
              <Link key={route.href} href={route.href} aria-current={isCurrent(route.href) ? "page" : undefined}>
                {route.name}
              </Link>
            ))}
          </>
        )}
      </nav>

      <div className="site-actions">
        <ConnectionStatus />
      </div>
    </header>
  );
}
