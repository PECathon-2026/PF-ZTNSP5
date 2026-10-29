"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, type PointerEvent as ReactPointerEvent } from "react";
import type { Mission } from "@/lib/types";

type HeroProps = {
  lastMission: Mission | null;
};

function prefersReducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function EntranceHero({ lastMission }: HeroProps) {
  const router = useRouter();
  const heroRef = useRef<HTMLElement>(null);
  const crossingRef = useRef(false);

  function onPointerMove(event: ReactPointerEvent<HTMLElement>) {
    if (prefersReducedMotion() || !heroRef.current) return;
    const rect = heroRef.current.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
    const y = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
    heroRef.current.style.setProperty("--px", x.toFixed(3));
    heroRef.current.style.setProperty("--py", y.toFixed(3));
  }

  function onPointerLeave() {
    if (!heroRef.current) return;
    heroRef.current.style.setProperty("--px", "0");
    heroRef.current.style.setProperty("--py", "0");
  }

  function crossTheGate(href: "/setup") {
    if (crossingRef.current) return;
    if (prefersReducedMotion() || !heroRef.current) {
      void router.push(href);
      return;
    }
    crossingRef.current = true;
    heroRef.current.classList.add("is-crossing");
    window.setTimeout(() => {
      void router.push(href);
      window.setTimeout(() => {
        heroRef.current?.classList.remove("is-crossing");
        crossingRef.current = false;
      }, 500);
    }, 420);
  }

  return (
    <section
      className="hero"
      ref={heroRef}
      onPointerMove={onPointerMove}
      onPointerLeave={onPointerLeave}
      aria-labelledby="hero-title"
    >
      <div className="hero__copy">
        <p className="hero__kicker">
          <span className="hero__kicker-seal" aria-hidden="true" />
          AUTONOMOUS ENGINEERING GUILD
        </p>
        <p className="hero__wordmark">
          KAGE <span>AI</span>
        </p>
        <h1 id="hero-title" className="hero__title">
          Your Code.
          <br />
          Our Guild.
          <br />
          <em>Verified Results.</em>
        </h1>
        <p className="hero__lede">
          A multi-agent engineering workspace that plans, implements, tests, reviews, and verifies
          software changes before you approve them.
        </p>

        <div className="hero__actions">
          <button type="button" className="btn btn--primary btn--lg" onClick={() => crossTheGate("/setup")}>
            INITIALIZE MISSION
            <span aria-hidden="true">→</span>
          </button>
          <Link href="/setup?focus=repository" className="btn btn--ghost btn--lg">
            CONNECT A REPOSITORY
          </Link>
        </div>

        {lastMission && (
          <Link href={`/missions/${lastMission.id}`} className="hero__last">
            <span className="mono">Continue where you left off</span>
            <span className="hero__last-id">{lastMission.id}</span>
            <span aria-hidden="true">↗</span>
          </Link>
        )}

        <p className="hero__rule">
          Build in the shadows. <span>Prove in the light.</span>
        </p>
      </div>

      <div className="hero__art" aria-hidden="true">
        <div className="art-stage">
          <img
            src="/images/entrance-night.jpg"
            alt=""
            className="art-photo"
            width={1600}
            height={900}
            fetchPriority="high"
          />
          <div className="art-grade" />
          <div className="art-mist art-mist--far" />
          <div className="art-mist art-mist--near" />
          <div className="art-gate">
            <span className="art-gate__pillar art-gate__pillar--left" />
            <span className="art-gate__pillar art-gate__pillar--right" />
            <span className="art-gate__beam art-gate__beam--top" />
            <span className="art-gate__beam art-gate__beam--lower" />
            <span className="art-gate__brace art-gate__brace--left" />
            <span className="art-gate__brace art-gate__brace--right" />
          </div>
          <div className="art-shoji art-shoji--left">
            <span />
            <span />
            <span />
          </div>
          <div className="art-shoji art-shoji--right">
            <span />
            <span />
            <span />
          </div>
          <div className="art-disc" />
          <p className="art-caption">
            <span>影</span> THE THRESHOLD
          </p>
        </div>
      </div>
    </section>
  );
}
