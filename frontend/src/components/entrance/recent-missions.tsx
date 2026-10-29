"use client";

import Link from "next/link";
import type { Mission } from "@/lib/types";
import { formatRelative, missionMeta } from "@/lib/status";

type RecentMissionsProps = {
  missions: Mission[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
};

export function RecentMissions({ missions, loading, error, onRetry }: RecentMissionsProps) {
  return (
    <section className="entrance-block" aria-labelledby="recent-title">
      <header className="block-head">
        <div>
          <p className="block-index">01 / MISSION LOG</p>
          <h2 id="recent-title">Recent missions</h2>
        </div>
        <Link href="/missions" className="text-link">
          Open the full log <span aria-hidden="true">→</span>
        </Link>
      </header>

      {loading && (
        <div className="mission-rows" aria-busy="true" aria-label="Loading missions">
          {[0, 1, 2].map((index) => (
            <div className="mission-row mission-row--skeleton" key={index}>
              <span className="skeleton" style={{ width: "8.5rem", height: "1rem" }} />
              <span className="skeleton" style={{ flex: 1, height: "1rem" }} />
              <span className="skeleton" style={{ width: "6rem", height: "1rem" }} />
            </div>
          ))}
        </div>
      )}

      {!loading && error && (
        <div className="state-block state-block--error" role="alert">
          <span className="state-mark" aria-hidden="true">
            ×
          </span>
          <h3>The mission log could not be read</h3>
          <p>{error}</p>
          <button type="button" className="btn btn--ghost" onClick={onRetry}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && missions.length === 0 && (
        <div className="state-block">
          <span className="state-mark" aria-hidden="true">
            影
          </span>
          <h3>No missions have been initialized</h3>
          <p>
            Missions appear here once the guild is given a repository and a request. Nothing is
            pre-filled — the log only shows work that actually exists.
          </p>
          <Link href="/setup" className="btn btn--primary">
            Initialize a mission
          </Link>
        </div>
      )}

      {!loading && !error && missions.length > 0 && (
        <ul className="mission-rows">
          {missions.slice(0, 6).map((mission) => {
            const meta = missionMeta(mission.status);
            return (
              <li key={mission.id}>
                <Link href={`/missions/${mission.id}`} className="mission-row">
                  <span className="mission-row__status">
                    <span className={`status`} data-tone={meta.tone}>
                      {meta.glyph} {meta.label}
                    </span>
                  </span>
                  <span className="mission-row__id mono">{mission.id}</span>
                  <span className="mission-row__request">{mission.request_text}</span>
                  <span className="mission-row__time subtle">{formatRelative(mission.created_at)}</span>
                  <span className="mission-row__go" aria-hidden="true">
                    →
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
