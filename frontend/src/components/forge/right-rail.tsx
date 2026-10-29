"use client";

import { GUILD } from "@/lib/status";
import { formatInstant } from "@/lib/status";
import type { Mission } from "@/lib/types";

type RightRailProps = {
  mission: Mission;
  candidateState: { id: string; fingerprint: string; state: string } | null;
  changedFiles: string[];
  loadingCandidate: boolean;
  candidateError: string | null;
  onRetry: () => void;
  onOpenFile: (path: string) => void;
};

export function RightRail({
  mission,
  candidateState,
  changedFiles,
  loadingCandidate,
  candidateError,
  onRetry,
  onOpenFile,
}: RightRailProps) {
  return (
    <section className="panel forge-rail" aria-labelledby="rail-title">
      <div className="panel-head">
        <span className="panel-title" id="rail-title">
          GUILD &amp; CANDIDATE
        </span>
      </div>

      <ul className="forge-rail__roster" aria-label="Guild roles">
        {GUILD.map((member) => (
          <li key={member.id} className="forge-rail__roster-item">
            <span className="forge-rail__glyph" aria-hidden="true">
              {member.glyph}
            </span>
            <span className="forge-rail__name">{member.name}</span>
          </li>
        ))}
      </ul>

      <div className="forge-rail__divider" />

      <div className="forge-rail__candidate">
        {loadingCandidate ? (
          <div className="state-block" aria-busy="true" style={{ padding: "0.5rem 0.7rem" }}>
            <span className="spinner" aria-hidden="true" />
            <p style={{ margin: "0.2rem 0 0", fontSize: "var(--text-xs)" }}>Reading candidate…</p>
          </div>
        ) : candidateError ? (
          <div className="state-block state-block--error" role="alert" style={{ padding: "0.5rem 0.7rem" }}>
            <span className="state-mark" aria-hidden="true">×</span>
            <p style={{ margin: "0.2rem 0 0", fontSize: "var(--text-xs)" }}>{candidateError}</p>
            <button type="button" className="btn btn--ghost btn--sm" style={{ marginTop: "0.4rem" }} onClick={onRetry}>
              Retry
            </button>
          </div>
        ) : candidateState ? (
          <>
            <p className="forge-rail__label">Active candidate</p>
            <p className="forge-rail__id mono">{candidateState.id}</p>
            <p className="forge-rail__fingerprint mono">{candidateState.fingerprint.slice(0, 16)}…</p>
            <span className="status" data-tone="plain">
              {candidateState.state}
            </span>
            {changedFiles.length > 0 && (
              <>
                <p className="forge-rail__label">Changed files</p>
                <ul className="forge-rail__files">
                  {changedFiles.map((path) => (
                    <li key={path} className="forge-rail__file mono" title={path} onClick={() => onOpenFile(path)}>
                      {path.length > 38 ? `${path.slice(0, 38)}…` : path}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        ) : (
          <div className="state-block state-block--inline" style={{ padding: "0.6rem 0.7rem" }}>
            <span className="state-mark" aria-hidden="true">影</span>
            <h3 style={{ margin: "0 0 0.3rem", fontSize: "var(--text-xs)" }}>No candidate yet</h3>
            <p style={{ margin: 0, fontSize: "var(--text-xs)" }}>
              The Samurai has not proposed a change for this mission. The forge shows repository
              files read-only until a candidate exists.
            </p>
          </div>
        )}
      </div>

      <p className="forge-rail__note" style={{ marginTop: "auto" }}>
        Opened {formatInstant(mission.created_at)} · last update {formatInstant(mission.updated_at)}
      </p>
    </section>
  );
}
