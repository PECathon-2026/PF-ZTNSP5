"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { useMissionDetail } from "@/lib/use-missions";
import { briefFromMission, useMissionBriefSync } from "@/components/shell/mission-context";
import { missionMeta, shortPath } from "@/lib/status";
import { languageOf } from "@/lib/status";
import { Explorer } from "./explorer";
import { ForgeEditor } from "./editor";
import { RightRail } from "./right-rail";
import { BottomPanel } from "./bottom-panel";

export function ForgeScreen({ missionId }: { missionId: string }) {
  const { mission, tasks, loading, notFound, error, reload } = useMissionDetail(missionId);
  const brief = useMemo(() => (mission ? briefFromMission(mission) : null), [mission]);
  useMissionBriefSync(brief);

  const [treePaths, setTreePaths] = useState<string[] | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [treeBusy, setTreeBusy] = useState(false);

  const [openTabs, setOpenTabs] = useState<string[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [contents, setContents] = useState<Record<string, string>>({});
  const [contentErrors, setContentErrors] = useState<Record<string, string>>({});

  const [candidate, setCandidate] = useState<{ id: string; fingerprint: string; state: string } | null>(null);
  const [unifiedDiff, setUnifiedDiff] = useState<string | null>(null);
  const [changedFiles, setChangedFiles] = useState<string[]>([]);
  const [candidateBusy, setCandidateBusy] = useState(false);
  const [candidateError, setCandidateError] = useState<string | null>(null);

  const refetchTree = useCallback(() => {
    if (!mission) return;
    setTreeBusy(true);
    setTreeError(null);
    api
      .repositoryTree(mission.repository_id)
      .then((paths) => {
        if (!mission) return;
        setTreePaths(paths);
      })
      .catch((caught) => {
        if (!mission) return;
        setTreeError(caught instanceof Error ? caught.message : "The repository tree could not be read.");
      })
      .finally(() => setTreeBusy(false));
  }, [mission]);

  useEffect(() => {
    if (!mission) return;
    let cancelled = false;
    refetchTree();
    if (!mission.active_candidate_id) return;
    setCandidateBusy(true);
    api
      .missionReport(missionId)
      .then((report) => {
        if (cancelled) return;
        const found = report.candidates.find((c) => c.id === mission.active_candidate_id);
        if (!found) return;
        setCandidate({ id: found.id, fingerprint: found.content_fingerprint, state: found.state });
        return api.candidateDiff(missionId, found.id, mission.repository_id);
      })
      .then((diff) => {
        if (cancelled || !diff) return;
        setChangedFiles(diff.files.map((file) => file.file_path));
        setUnifiedDiff(diff.unified_diff ?? null);
      })
      .catch((caught) => {
        if (cancelled) return;
        setCandidateError(caught instanceof Error ? caught.message : "The candidate could not be read.");
      })
      .finally(() => setCandidateBusy(false));
    return () => {
      cancelled = true;
    };
  }, [mission, missionId, refetchTree]);

  const taskCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const task of tasks) counts[task.status] = (counts[task.status] ?? 0) + 1;
    return counts;
  }, [tasks]);

  function openFile(path: string) {
    if (!mission) return;
    setOpenTabs((previous) => (previous.includes(path) ? previous : [...previous, path]));
    setActivePath(path);
    if (contents[path] !== undefined || contentErrors[path]) return;
    api
      .repositoryFile(mission.repository_id, path)
      .then((file) => {
        setContents((previous) => ({ ...previous, [path]: file.content }));
        setContentErrors((previous) => {
          const next = { ...previous };
          delete next[path];
          return next;
        });
      })
      .catch((caught) => {
        setContentErrors((previous) => ({ ...previous, [path]: (caught as Error).message }));
      });
  }

  function closeTab(path: string, event: React.MouseEvent) {
    event.stopPropagation();
    setOpenTabs((previous) => previous.filter((p) => p !== path));
    if (activePath === path) {
      const remaining = openTabs.filter((p) => p !== path);
      setActivePath(remaining.length > 0 ? remaining[remaining.length - 1] : null);
    }
  }

  const content = activePath ? contents[activePath] : null;
  const contentError = activePath ? contentErrors[activePath] : null;
  const language = activePath ? languageOf(activePath) : "plaintext";

  if (notFound) {
    return (
      <div className="content-width forge-page">
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
      <div className="content-width forge-page">
        <div className="state-block" aria-busy="true">
          <span className="spinner" aria-hidden="true" />
          <p>Opening the forge for {missionId}…</p>
        </div>
      </div>
    );
  }

  if (!mission) {
    return (
      <div className="content-width forge-page">
        <div className="state-block state-block--error" role="alert">
          <span className="state-mark" aria-hidden="true">×</span>
          <h3>Mission could not be read</h3>
          <p>{error ?? "The backend did not return this mission."}</p>
          <button type="button" className="btn btn--ghost" onClick={reload}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="content-width forge-page">
      <header className="forge-bar panel">
        <Link className="forge-bar__back text-link" href="/missions">← missions</Link>
        <div className="forge-bar__identity">
          <p className="forge-bar__id mono">{mission.id}</p>
          <p className="forge-bar__meta">
            <span className="status" data-tone={missionMeta(mission.status).tone}>
              {missionMeta(mission.status).glyph} {mission.status}
            </span>
            <span className="muted">{shortPath(mission.repository_id, 1)}</span>
          </p>
        </div>
        <Link className="btn btn--ghost btn--sm" href={`/missions/${mission.id}`}>
          Command center
        </Link>
      </header>

      <div className="forge-grid">
        <Explorer
          paths={treePaths ?? []}
          repositoryHint={mission.repository_id}
          error={treeError}
          onRetry={refetchTree}
          onOpen={openFile}
        />

        <section className="panel editor-zone" aria-labelledby="editor-title">
          <div className="panel-head" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
            <span className="panel-title" id="editor-title">EDITOR</span>
            {candidate && (
              <button type="button" className="btn btn--quiet btn--sm" onClick={() => setActivePath(null)}>
                Show candidate diff
              </button>
            )}
          </div>
          <div className="editor-tabs-wrap" style={{ flex: "0 0 auto" }}>
            <div className="tabs" role="tablist" aria-label="Open files">
              {openTabs.map((path) => {
                const active = path === activePath;
                const basename = path.split(/[\\/]/).pop() ?? path;
                return (
                  <button
                    key={path}
                    type="button"
                    role="tab"
                    id={`forge-tab-${encodeURIComponent(path)}`}
                    aria-selected={active}
                    aria-controls={`forge-panel-${encodeURIComponent(path)}`}
                    className="tab"
                    onClick={() => setActivePath(path)}
                  >
                    {basename}
                    {contentErrors[path] ? <span className="editor-tab__warn" title={contentErrors[path]}>⚠</span> : null}
                    <button type="button" className="editor-tab__close" aria-label={`Close ${path}`} onClick={(event) => closeTab(path, event)}>
                      ×
                    </button>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="editor-content">
            {activePath && contentError && (
              <div className="state-block state-block--error" role="alert" style={{ padding: "0.9rem" }}>
                <span className="state-mark" aria-hidden="true">×</span>
                <h3 style={{ margin: "0 0 0.3rem", fontSize: "var(--text-xs)" }}>Cannot read file</h3>
                <p style={{ margin: 0, fontSize: "var(--text-xs)" }}>{contentError}</p>
              </div>
            )}
            {activePath && content !== undefined && contentErrors[activePath] === undefined && (
              <>
                <p className="editor-path mono" title={activePath}>{activePath}</p>
                <ForgeEditor value={content ?? ""} language={language} height="100%" />
              </>
            )}
            {!activePath && candidate && unifiedDiff !== null && (
              <div className="forge-diff">
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{unifiedDiff}</pre>
              </div>
            )}
            {!activePath && !(candidate && unifiedDiff !== null) && (
              <div className="state-block state-block--inline" style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", textAlign: "center" }}>
                <span className="state-mark" aria-hidden="true">▢</span>
                <h3 style={{ margin: "0.3rem 0 0", fontSize: "var(--text-xs)" }}>Open a file from the repository</h3>
                <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--color-text-subtle)" }}>
                  Files open read-only. The Samurai proposes changes as a candidate you can review
                  here before any approval.
                </p>
              </div>
            )}
          </div>
        </section>

        <RightRail
          mission={mission}
          candidateState={candidate}
          changedFiles={changedFiles}
          loadingCandidate={candidateBusy}
          candidateError={candidateError}
          onRetry={reload}
          onOpenFile={openFile}
        />
      </div>

      <BottomPanel status={mission.status} taskCounts={taskCounts} />
    </div>
  );
}
