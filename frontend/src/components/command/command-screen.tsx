"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useMissionDetail, useMissionEvents } from "@/lib/use-missions";
import { briefFromMission, useMissionBriefSync } from "@/components/shell/mission-context";
import { MissionHeaderBar } from "./mission-header-bar";
import { GuildRail } from "./guild-rail";
import { Timeline } from "./timeline";
import { MissionInspector } from "./mission-inspector";

export function CommandScreen({ missionId }: { missionId: string }) {
  const { mission, criteria, tasks, loading, notFound, error, reload } = useMissionDetail(missionId);
  const events = useMissionEvents(missionId, Boolean(mission) && !notFound);
  const brief = useMemo(() => (mission ? briefFromMission(mission) : null), [mission]);
  useMissionBriefSync(brief);

  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function confirmCancelMission() {
    setCancelling(true);
    setCancelError(null);
    try {
      await api.cancelMission(missionId);
      setConfirmCancel(false);
      reload();
    } catch (caught) {
      setCancelError(caught instanceof ApiError ? caught.detail : "The cancel request could not be recorded.");
    } finally {
      setCancelling(false);
    }
  }

  if (notFound) {
    return (
      <div className="content-width command-page">
        <div className="state-block state-block--error" role="alert">
          <span className="state-mark" aria-hidden="true">
            ×
          </span>
          <h3>Mission not found</h3>
          <p>
            The backend has no mission with id <span className="mono">{missionId}</span>. It may have
            been removed, or the id may be mistyped.
          </p>
          <Link className="btn btn--ghost" href="/missions">
            Back to missions
          </Link>
        </div>
      </div>
    );
  }

  if (loading && !mission) {
    return (
      <div className="content-width command-page">
        <div className="state-block" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Reading mission {missionId}…</p>
        </div>
      </div>
    );
  }

  if (!mission) {
    return (
      <div className="content-width command-page">
        <div className="state-block state-block--error" role="alert">
          <span className="state-mark" aria-hidden="true">
            ×
          </span>
          <h3>Mission could not be read</h3>
          <p>{error ?? "The backend did not return this mission."}</p>
          <button type="button" className="btn btn--ghost" onClick={reload}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const planningHonesty =
    mission.status === "PLANNING" ||
    mission.status === "CREATED" ||
    mission.status === "PREFLIGHT" ||
    mission.status === "READY_FOR_AUTHORIZATION";

  return (
    <div className="content-width command-page">
      <MissionHeaderBar
        mission={mission}
        criteria={criteria}
        tasks={tasks}
        repositoryHint={null}
        onCancel={() => {
          setCancelError(null);
          setConfirmCancel(true);
        }}
        cancelling={cancelling}
      />

      {error && (
        <p className="field-error command-refresh-error" role="alert">
          {error} Retrying automatically.
        </p>
      )}

      {planningHonesty && (
        <div className="command-notice" role="status">
          <span className="command-notice__mark" aria-hidden="true">
            影
          </span>
          <div>
            <p className="command-notice__title">Recorded, not yet executed</p>
            <p>
              The mission and its brief are stored with the backend. This build does not run the
              orchestration engine, so the timeline stays quiet and no checks execute until an
              execution runtime is connected. Everything shown here is exactly what the backend
              reports — nothing is simulated.
            </p>
          </div>
        </div>
      )}

      <div className="command-grid">
        <GuildRail tasks={tasks} status={mission.status} />
        <Timeline events={events} />
        <MissionInspector mission={mission} criteria={criteria} tasks={tasks} />
      </div>

      {confirmCancel && (
        <div className="dialog-scrim" role="presentation" onClick={() => !cancelling && setConfirmCancel(false)}>
          <div
            className="dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="cancel-dialog-title"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="cancel-dialog-title">Cancel this mission?</h2>
            <p className="muted">
              The backend will mark <span className="mono">{mission.id}</span> as cancellation
              requested. Work already recorded — events, tasks, criteria — stays visible for review.
              This cannot be undone.
            </p>
            {cancelError && (
              <p className="field-error" role="alert">
                {cancelError}
              </p>
            )}
            <div className="dialog-actions">
              <button type="button" className="btn btn--quiet" onClick={() => setConfirmCancel(false)} disabled={cancelling}>
                Keep mission
              </button>
              <button type="button" className="btn btn--danger" onClick={() => void confirmCancelMission()} disabled={cancelling}>
                {cancelling ? <span className="btn-spinner" aria-hidden="true" /> : null}
                {cancelling ? "Requesting…" : "Cancel mission"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
