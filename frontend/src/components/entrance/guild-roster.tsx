"use client";

import { GUILD, LIFECYCLE, VERIFIER_IDENTITY } from "@/lib/status";

export function GuildRoster() {
  return (
    <section className="entrance-block" aria-labelledby="guild-title">
      <header className="block-head">
        <div>
          <p className="block-index">02 / THE GUILD</p>
          <h2 id="guild-title">Four roles. One verifier.</h2>
        </div>
        <p className="block-aside">
          Every themed name is paired with the function it performs. No agent speaks for the
          evidence.
        </p>
      </header>

      <ul className="guild-grid">
        {GUILD.map((agent) => (
          <li key={agent.id} className="guild-card">
            <span className="guild-card__glyph" aria-hidden="true">
              {agent.glyph}
            </span>
            <div className="guild-card__body">
              <p className="guild-card__name">{agent.name}</p>
              <p className="guild-card__role">{agent.role}</p>
              <p className="guild-card__purpose">{agent.purpose}</p>
            </div>
          </li>
        ))}
        <li className="guild-card guild-card--verifier">
          <span className="guild-card__glyph" aria-hidden="true">
            {VERIFIER_IDENTITY.glyph}
          </span>
          <div className="guild-card__body">
            <p className="guild-card__name">{VERIFIER_IDENTITY.name}</p>
            <p className="guild-card__role">{VERIFIER_IDENTITY.role}</p>
            <p className="guild-card__purpose">{VERIFIER_IDENTITY.purpose}</p>
          </div>
        </li>
      </ul>
    </section>
  );
}

export function MissionLifecycle() {
  return (
    <section className="entrance-block entrance-block--lifecycle" aria-labelledby="lifecycle-title">
      <header className="block-head">
        <div>
          <p className="block-index">03 / THE METHOD</p>
          <h2 id="lifecycle-title">Evidence before approval</h2>
        </div>
        <p className="block-aside">Your approval is the final step, not a formality.</p>
      </header>

      <ol className="lifecycle">
        {LIFECYCLE.map((stage, index) => (
          <li key={stage.key}>
            <span className="lifecycle__index">{String(index + 1).padStart(2, "0")}</span>
            <span className="lifecycle__label">{stage.label}</span>
            <span className="lifecycle__detail">{stage.detail}</span>
          </li>
        ))}
      </ol>

      <blockquote className="trust-statement">
        <p>
          Engineering claims in KAGE are tied to execution evidence — recorded checks, diffs,
          findings, and verification results bound to an exact candidate. Nothing is asserted
          without a record.
        </p>
        <footer>The guild&apos;s rule</footer>
      </blockquote>
    </section>
  );
}
