"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useMissionReport } from "@/lib/use-missions";
import { briefFromMission, useMissionBriefSync } from "@/components/shell/mission-context";
import { criterionMeta, formatInstant, formatElapsed, missionMeta, shortPath } from "@/lib/status";

type EvidenceScreenProps = {
  missionId: string;
};

function renderCommand(command: unknown): string {
  if (Array.isArray(command)) return command.join(" ");
  if (typeof command === "string") return command;
  return String(command);
}

export function EvidenceScreen({ missionId }: EvidenceScreenProps) {
  const { report, loading, notFound, error, reload } = useMissionReport(missionId);
  const mission = report?.mission ?? null;
  const criteria = report?.criteria ?? [];
  const evidence = report?.evidence ?? [];
  const findings = report?.findings ?? [];
  const approvals = report?.approvals ?? [];
  const brief = useMemo(() => (mission ? briefFromMission(mission) : null), [mission]);
  useMissionBriefSync(brief);

  const passed = criteria.filter((criterion) => criterion.status === "PASS").length;
  const failed = criteria.filter((criterion) => criterion.status === "FAIL" || criterion.status === "BLOCKED").length;

  if (notFound) {
    return (
      <div className="content-width evidence-page">
        <div className="state-block state-block--error" role="alert">
          <span className="state-mark" aria-hidden="true">×</span>
          <h3>Mission not found</h3>
          <p>The backend has no mission with id <span className="mono">{missionId}</span>.</p>
          <Link className="btn btn--ghost" href="/missions">Back to missions</Link>
        </div>
      </div>
    );
  }

  if (loading && !mission) {
    return (
      <div className="content-width evidence-page">
        <div className="state-block" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Opening the evidence desk for {missionId}…</p>
        </div>
      </div>
    );
  }

  if (!mission) {
    return (
      <div className="content-width evidence-page">
        <div className="state-block state-block--error" role="alert">
          <span className="state-mark" aria-hidden="true">×</span>
          <h3>Evidence report could not be read</h3>
          <p>{error ?? "The backend did not return this mission's report."}</p>
          <button type="button" className="btn btn--ghost" onClick={reload}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="content-width evidence-page">
      <header className="evidence-head panel">
        <Link className="evidence-head__back text-link" href={`/missions/${missionId}`}>
          ← command center
        </Link>
        <div className="evidence-head__identity">
          <p className="evidence-head__id mono">{mission.id}</p>
          <p className="evidence-head__meta">
            <span className="status" data-tone={missionMeta(mission.status).tone}>
              {missionMeta(mission.status).glyph} {mission.status}
            </span>
            <span className="muted">{shortPath(mission.repository_id, 1)} · {formatElapsed(mission.created_at)}</span>
          </p>
        </div>
      </header>

      <p className="evidence__intro">
        The verifier checks each acceptance criterion against recorded evidence. Nothing here is
        simulated: every row is what the backend actually reports for this mission.
      </p>

      <section className="evidence-section panel" aria-labelledby="evidence-title">
        <div className="panel-head" id="evidence-title">
          <span className="panel-title">EVIDENCE</span>
          <span className="evidence-section__meta mono">{evidence.length} checked run{evidence.length === 1 ? "" : "s"}</span>
        </div>
        <p className="evidence-section__desc">
          Sentinel runs the authorized checks and records every run here: the command, exit code,
          duration, and artifact fingerprint.
        </p>
        {evidence.length === 0 ? (
          <div className="state-block state-block--inline">
            <span className="state-mark" aria-hidden="true">影</span>
            <h3>No checks have run yet</h3>
            <p>
              No orchestration runtime is connected to this build, so Sentinel has nothing to check.
              Evidence appears here the first time a check runs against a candidate.
            </p>
          </div>
        ) : (
          <ul className="evidence-list">
            {evidence.map((item) => (
              <li key={item.id} className="evidence-item">
                <div className="evidence-item__head">
                  <span className="evidence-item__kind mono">{item.kind}</span>
                  <span className="evidence-item__source mono">{item.source}</span>
                </div>
                <p className="evidence-item__command mono">{renderCommand(item.command)}</p>
                <div className="evidence-item__meta mono">
                  <span>exit {item.exit_code ?? "—"}</span>
                  {item.duration_ms != null && <span>{item.duration_ms} ms</span>}
                  <span>{item.fingerprint.slice(0, 14)}…</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="evidence-section panel" aria-labelledby="findings-title">
        <div className="panel-head" id="findings-title">
          <span className="panel-title">FINDINGS</span>
          <span className="evidence-section__meta mono">{findings.length} filed</span>
        </div>
        <p className="evidence-section__desc">
          The Shadow Council inspects candidate diffs for regressions, correctness, and security
          concerns, then files structured findings here.
        </p>
        {findings.length === 0 ? (
          <div className="state-block state-block--inline">
            <span className="state-mark" aria-hidden="true">◈</span>
            <h3>No review findings yet</h3>
            <p>
              Without a candidate to review, the Shadow Council has nothing to inspect. Findings
              appear here once a candidate exists and review runs.
            </p>
          </div>
        ) : (
          <ul className="findings-list">
            {findings.map((finding) => (
              <li key={finding.id} className="finding-item">
                <div className="finding-item__head">
                  <span className="finding-item__source mono">{finding.source_agent}</span>
                  <span className="status" data-tone={finding.severity.toLowerCase() === "high" ? "red" : "warn"}>
                    {finding.severity}
                  </span>
                </div>
                <h4 className="finding-item__title">{finding.title}</h4>
                <p className="finding-item__desc">{finding.description}</p>
                <p className="finding-item__meta mono">
                  {finding.file_path ? `${finding.file_path}:${finding.line_start ?? "?"}` : "no file"}
                  <span>status {finding.status}</span>
                  {finding.evidence_ids.length > 0 && <span>{finding.evidence_ids.length} evidence</span>}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="evidence-section panel evidence-section--approval" aria-labelledby="approval-title">
        <div className="panel-head" id="approval-title">
          <span className="panel-title">APPROVAL</span>
          <span className="evidence-section__meta mono">{approvals.length} recorded</span>
        </div>
        <p className="evidence-section__desc">
          Your decision gates whether a candidate is applied to the repository. Approve or reject —
          nothing lands without you.
        </p>
        <div className="approval-unavailable" role="status">
          <span className="state-mark" aria-hidden="true">核</span>
          <div>
            <h3>Approval is not available in this build</h3>
            <p>
              The backend does not expose approve/apply/reject endpoints, and no candidate can be
              applied until the orchestration runtime is connected. When those endpoints exist, you
              will review the candidate diff here and decide whether to apply it.
            </p>
            {approvals.length > 0 && (
              <div className="approval-unavailable__history">
                <h4>Recorded approvals</h4>
                <ul>
                  {approvals.map((approval) => (
                    <li key={approval.id} className="approval-item">
                      <span className="approval-item__decision mono">{approval.decision}</span>
                      <span className="approval-item__action mono">{approval.intended_action}</span>
                      <span className="approval-item__when mono">{formatInstant(approval.decided_at)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </section>

      <p className="evidence__criteria-summary mono">
        {criteria.length === 0
          ? "No acceptance criteria were recorded with this mission."
          : `${passed} pass${passed !== 1 ? "es" : ""} · ${failed} fail/blocked · ${criteria.length} total`}
      </p>
    </div>
  );
}
