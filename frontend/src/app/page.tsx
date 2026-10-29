import Link from "next/link";
import { HealthStatus } from "@/components/health-status";
import { LandingExperience } from "@/components/landing/landing-experience";
import "./landing.css";

export default function HomePage() {
  return <>
    <LandingExperience />
    <div className="content-width">
      <section className="editorial-section about-project" aria-labelledby="about-title"><div className="section-heading"><p className="eyebrow">03 · ABOUT KAGE AI</p><h2 id="about-title">More than a message.<br /><em>A mission.</em></h2></div><div className="about-project-copy"><p>KAGE AI is a local engineering workspace designed to turn a natural-language request into a reviewed change to an existing codebase.</p><p>Shogun plans, Samurai implements, Sentinel tests, and Shadow Council reviews. Independent verification ties the evidence to the exact candidate before a human decides whether to apply it.</p><Link href="/setup" className="text-action">Define a mission ↗</Link></div></section>
      <section className="editorial-section method-section" aria-labelledby="method-title"><div className="section-heading"><p className="eyebrow">04 · THE METHOD</p><h2 id="method-title">Evidence before<br /><em>approval.</em></h2><p>Plan → Build → Test → Review → Verify → Approve. Your approval is the final step, not a formality.</p></div><div className="method-steps"><span>01 / Plan</span><span>02 / Build</span><span>03 / Test</span><span>04 / Review</span><span>05 / Verify</span><span>06 / Approve</span></div></section>
      <section className="editorial-section readiness-section" aria-labelledby="readiness-title"><div className="section-heading"><p className="eyebrow">05 · READINESS</p><h2 id="readiness-title">Before the mission.</h2><p>Only confirmed capability earns a ready state. No results or activity are invented.</p></div><div className="readiness-list"><HealthStatus detailed /><div className="readiness-row"><span className="status-pip" aria-hidden="true" /><div><strong>Model connection</strong><p>No model readiness contract is available yet.</p></div><span className="readiness-label">Unverified</span></div><div className="readiness-row"><span className="status-pip" aria-hidden="true" /><div><strong>Execution environment</strong><p>No execution readiness contract is available yet.</p></div><span className="readiness-label">Unverified</span></div></div></section>
      <section className="editorial-section" aria-labelledby="archive-title"><div className="section-heading"><p className="eyebrow">06 · THE ARCHIVE</p><h2 id="archive-title">Missions, remembered.</h2></div><div className="archive-empty"><span aria-hidden="true">影</span><div><h3>No mission history yet</h3><p>Saved missions and their actual outcomes will appear when a mission backend is connected.</p><Link href="/setup" className="text-action">Prepare a mission ↗</Link></div></div></section>
    </div>
  </>;
}
