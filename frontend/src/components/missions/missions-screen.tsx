"use client";

import Link from "next/link";
import { useState } from "react";
import { useMissions } from "@/lib/use-missions";
import { missionMeta, formatInstant } from "@/lib/status";

export function MissionsScreen() {
  const { missions, loading, error, reload } = useMissions();
  const [statusFilter, setStatusFilter] = useState<"ALL" | "PLANNING" | "ACTIVE" | "TERMINAL">("ALL");

  const activeStatuses = ["RUNNING", "CHECKING", "REPAIRING", "REVIEWING", "VERIFYING", "APPLYING"];
  const terminalStatuses = [
    "APPLIED",
    "REJECTED",
    "CANCELLED",
    "BLOCKED",
    "BUDGET_EXHAUSTED",
    "INTERRUPTED",
    "FAILED_VERIFICATION",
  ];

  const filtered = missions.filter((mission) => {
    if (statusFilter === "ALL") return true;
    if (statusFilter === "PLANNING") return mission.status === "PLANNING";
    if (statusFilter === "ACTIVE") return activeStatuses.includes(mission.status);
    return terminalStatuses.includes(mission.status);
  });

  const counts: Record<string, number> = {
    ALL: missions.length,
    PLANNING: missions.filter((m) => m.status === "PLANNING").length,
    ACTIVE: missions.filter((m) => activeStatuses.includes(m.status)).length,
    TERMINAL: missions.filter((m) => terminalStatuses.includes(m.status)).length,
  };

  return (
    <div className="content-width missions-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">COMMAND CENTER</p>
          <h1>The mission roster</h1>
          <p className="lede">
            Every commissioned mission appears here with its lifecycle status. A mission is recorded
            once the guild accepts the brief — execution follows only when a runtime is connected.
          </p>
        </div>
      </header>

      <div className="missions-filter">
        {([ "ALL", "PLANNING", "ACTIVE", "TERMINAL" ] as const).map((filter) => (
          <button
            key={filter}
            type="button"
            className={`filter-chip ${statusFilter === filter ? "is-active" : ""}`}
            onClick={() => setStatusFilter(filter)}
          >
            {filter}
            <span className="chip-count mono">{counts[filter]}</span>
          </button>
        ))}
        <button
          type="button"
          className="btn btn--ghost btn--sm"
          onClick={reload}
          aria-label="Reload the mission roster"
        >
          Reload
        </button>
      </div>

      <div className="missions-table">
        <ul className="mission-list" aria-label="Commissioned missions">
          {loading && missions.length === 0 ? (
            <div className="state-block" aria-busy="true">
              <span className="spinner" aria-hidden="true" />
              <p>Loading missions from the guild records…</p>
            </div>
          ) : filtered.length === 0 ? (
            <div className="state-block state-block--inline">
              <span className="state-mark" aria-hidden="true">
                空
              </span>
              <h3>No commissioned missions yet</h3>
              <p>
                {error
                  ? `The roster could not be loaded: ${error}`
                  : "Commission your first mission from the mission desk."}
              </p>
              {!error && (
                <Link className="btn btn--primary" href="/setup">
                  Commission a mission
                </Link>
              )}
            </div>
          ) : (
            filtered.map((mission) => (
              <li key={mission.id}>
                <Link href={`/missions/${mission.id}`} className="mission-row">
                  <span className="mission-row__id mono">{mission.id}</span>
                  <span className="mission-row__status">
                    <span className="status" data-tone={missionMeta(mission.status).tone}>
                      {missionMeta(mission.status).glyph} {mission.status}
                    </span>
                  </span>
                  <span className="mission-row__request">{mission.request_text}</span>
                  <span className="mission-row__time mono">{formatInstant(mission.created_at)}</span>
                  <span aria-hidden="true" className="mission-row__go">
                    ↗
                  </span>
                </Link>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
