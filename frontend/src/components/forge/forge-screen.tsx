"use client";

import Link from "next/link";
import { ArrowLeft, ArrowUpRight, Code2, GitCompareArrows, Maximize2, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { api } from "@/lib/api";
import { useMissionDetail, useMissionEvents } from "@/lib/use-missions";
import { briefFromMission, useMissionBriefSync } from "@/components/shell/mission-context";
import { missionMeta, shortPath } from "@/lib/status";
import { languageOf } from "@/lib/status";
import { Explorer } from "./explorer";
import { ForgeEditor, ForgeDiffEditor } from "./editor";
import { FileContext } from "./file-context";
import { ActivityDock } from "@/components/cockpit/activity-dock";
import { EvidenceDetail } from "@/components/mission/evidence-detail";
import "@/components/cockpit/cockpit.css";
import "./workbench.css";
import { CommandPalette } from "./command-palette";
import { ResizeHandle } from "./resize-handle";

export function ForgeScreen({ missionId }: { missionId: string }) {
  const { detail, mission, tasks, loading, notFound, error, reload } = useMissionDetail(missionId);
  const events = useMissionEvents(missionId, Boolean(mission) && !notFound, reload);
  const openedLink = useRef("");
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [explorerWidth, setExplorerWidth] = useState(230);
  const [railWidth, setRailWidth] = useState(290);
  const [source, setSource] = useState<"candidate" | "original">("candidate");
  const [focusEditor, setFocusEditor] = useState(false);
  const [line, setLine] = useState(1);
  const [compare, setCompare] = useState(false);
  const [comparison, setComparison] = useState<{ original: string; modified: string } | null>(null);
  const [comparisonError, setComparisonError] = useState<string | null>(null);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const repositoryId = mission?.repository_id;
  const candidateId = mission?.active_candidate_id;
  useEffect(() => {
    function shortcut(event: KeyboardEvent) { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPaletteOpen((open) => !open); } }
    window.addEventListener("keydown", shortcut);
    try {
      const saved = JSON.parse(localStorage.getItem(`kage-forge-layout:${missionId}`) ?? "null");
      if (saved) { setExplorerWidth(Math.max(170, Math.min(330, Number(saved.explorer) || 230))); setRailWidth(Math.max(220, Math.min(380, Number(saved.rail) || 290))); }
    } catch { /* Use defaults when local storage is unavailable. */ }
    return () => window.removeEventListener("keydown", shortcut);
  }, [missionId]);
  function saveLayout(explorer: number, rail: number) {
    setExplorerWidth(explorer); setRailWidth(rail);
    try { localStorage.setItem(`kage-forge-layout:${missionId}`, JSON.stringify({ explorer, rail })); } catch { /* Resizing remains usable without persistence. */ }
  }
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
    if (!repositoryId) return;
    setTreeBusy(true);
    setTreeError(null);
    api
      .repositoryTree(repositoryId)
      .then((paths) => {
        setTreePaths(paths);
      })
      .catch((caught) => {
        setTreeError(caught instanceof Error ? caught.message : "The repository tree could not be read.");
      })
      .finally(() => setTreeBusy(false));
  }, [repositoryId]);

  useEffect(() => {
    if (!repositoryId) return;
    let cancelled = false;
    refetchTree();
    if (!candidateId) { setCandidate(null); setUnifiedDiff(null); setChangedFiles([]); return; }
    setCandidateBusy(true);
    api
      .missionReport(missionId)
      .then((report) => {
        if (cancelled) return;
        const found = report.candidate;
        if (!found) return;
        setCandidate({ id: found.id, fingerprint: found.content_fingerprint, state: found.state });
        return api.candidateDiff(missionId, found.id, repositoryId);
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
  }, [candidateId, repositoryId, missionId, refetchTree]);

  const sourceKey = source === "candidate" && candidateId ? `candidate:${candidateId}` : `repository:${repositoryId}`;
  const openFile = useCallback((path: string) => {
    if (!repositoryId) return;
    const cacheKey = `${sourceKey}:${path}`;
    setOpenTabs((previous) => (previous.includes(path) ? previous : [...previous, path]));
    setActivePath(path);
    setLine(1);
    try { sessionStorage.setItem(`kage-forge-file:${missionId}`, path); } catch { /* Navigation remains available without storage. */ }
    if (contents[cacheKey] !== undefined || contentErrors[cacheKey]) return;
    const fileRequest = source === "candidate" && candidateId
      ? api.candidateFile(missionId, candidateId, path)
      : api.repositoryFile(repositoryId, path);
    fileRequest
      .then((file) => {
        setContents((previous) => ({ ...previous, [cacheKey]: file.content }));
        setContentErrors((previous) => {
          const next = { ...previous };
          delete next[cacheKey];
          return next;
        });
      })
      .catch((caught) => {
        setContentErrors((previous) => ({ ...previous, [cacheKey]: (caught as Error).message }));
      });
  }, [repositoryId, sourceKey, candidateId, missionId, source, contents, contentErrors]);

  useEffect(() => {
    if (!repositoryId || openedLink.current === `${missionId}:${sourceKey}`) return;
    const paths = treePaths ?? detail?.repository_files ?? [];
    let file = new URLSearchParams(window.location.search).get("file");
    if (!file) {
      try { const saved = sessionStorage.getItem(`kage-forge-file:${missionId}`); if (saved && paths.includes(saved)) file = saved; } catch { /* Use the repository entry point. */ }
      file ??= changedFiles[0] ?? paths.find((path) => /(^|\/)readme\.md$/i.test(path)) ?? paths.find((path) => /(^|\/)(main\.py|index\.(tsx?|jsx?))$/.test(path)) ?? paths[0] ?? null;
    }
    if (!file) return;
    openedLink.current = `${missionId}:${sourceKey}`; openFile(file);
  }, [missionId, repositoryId, sourceKey, openFile, treePaths, detail?.repository_files, changedFiles]);

  useEffect(() => {
    if (!compare || !activePath || !candidateId || !repositoryId) return;
    const controller = new AbortController(); setComparison(null); setComparisonError(null);
    Promise.all([api.repositoryFile(repositoryId, activePath, controller.signal), api.candidateFile(missionId, candidateId, activePath, controller.signal)])
      .then(([original, modified]) => { if (!controller.signal.aborted) setComparison({ original: original.content, modified: modified.content }); })
      .catch((caught) => { if (!controller.signal.aborted) setComparisonError(caught instanceof Error ? caught.message : "The two sources could not be compared."); });
    return () => controller.abort();
  }, [compare, activePath, candidateId, repositoryId, missionId]);

  function closeTab(path: string, event: React.MouseEvent) {
    event.stopPropagation();
    setOpenTabs((previous) => previous.filter((p) => p !== path));
    if (activePath === path) {
      const remaining = openTabs.filter((p) => p !== path);
      setActivePath(remaining.length > 0 ? remaining[remaining.length - 1] : null);
    }
  }

  const activeCacheKey = `${sourceKey}:${activePath}`;
  const content = activePath ? contents[activeCacheKey] : null;
  const contentError = activePath ? contentErrors[activeCacheKey] : null;
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
    <div className="forge-workbench">
      <header className="cockpit-toolbar">
        <div className="cockpit-mission-id"><Link className="cockpit-icon-button" href={`/missions/${mission.id}`} aria-label="Return to mission field"><ArrowLeft size={17} /></Link><div><span className="mono">ENGINEERING WORKSPACE</span><h1>{mission.id}</h1></div><span className="status" data-tone={missionMeta(mission.status).tone}>{missionMeta(mission.status).label}</span></div>
        <div className="cockpit-toolbar-actions"><button className="cockpit-search-trigger" onClick={() => setPaletteOpen(true)}><Search size={15} /><span>Find file / command</span><kbd>Ctrl K</kbd></button>
          <button className="cockpit-icon-button" aria-label={focusEditor ? "Restore workspace" : "Focus editor"} aria-pressed={focusEditor} onClick={() => setFocusEditor((focused) => !focused)}><Maximize2 size={16} /></button>
          <Link className="btn btn--ghost btn--sm" href={`/missions/${mission.id}/evidence`}>Proof desk <ArrowUpRight size={14} /></Link><Link className="btn btn--primary btn--sm" href={`/missions/${mission.id}`}>Mission field <ArrowUpRight size={14} /></Link></div>
      </header>

      <div className={`forge-grid forge-grid--resizable${focusEditor ? " is-editor-focused" : ""}`} style={{ "--explorer-width": `${explorerWidth}px`, "--rail-width": `${railWidth}px` } as CSSProperties}>
        <Explorer
          paths={Array.from(new Set([...(treePaths ?? detail?.repository_files ?? []), ...changedFiles]))}
          repositoryHint={mission.repository_id}
          error={treeError}
          onRetry={refetchTree}
          onOpen={openFile}
          activePath={activePath}
          changedFiles={changedFiles}
        />
        <ResizeHandle label="Explorer width" value={explorerWidth} min={170} max={330} onChange={(next) => saveLayout(next, railWidth)} />

        <section className="panel editor-zone" aria-labelledby="editor-title">
          <div className="code-toolbar">
            <span className="mono" id="editor-title"><Code2 size={14} /> SOURCE CANVAS</span>
            <div className="code-view-controls"><button aria-pressed={!compare} onClick={() => setCompare(false)}>Read source</button><button aria-pressed={compare} disabled={!candidate || !activePath} title={!candidate ? "Comparison requires a frozen candidate" : "Compare original repository with frozen candidate"} onClick={() => setCompare(true)}><GitCompareArrows size={13} /> Compare</button></div>
            {candidate && <label className="code-source-label">Source <select value={source} onChange={(event) => { setSource(event.target.value as "candidate" | "original"); setCompare(false); setContents({}); setContentErrors({}); setActivePath(null); setOpenTabs([]); }}><option value="candidate">Frozen candidate</option><option value="original">Original repository</option></select></label>}
            {candidate && <button className="code-patch-button" onClick={() => { setActivePath(null); setCompare(false); }}>Patch</button>}
          </div>
          <div className="editor-tabs-wrap" style={{ flex: "0 0 auto" }}>
            <div className="tabs" role={openTabs.length ? "tablist" : undefined} aria-label={openTabs.length ? "Open files" : undefined}>
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
                    aria-controls="forge-editor-panel"
                    tabIndex={active || (!activePath && path === openTabs[0]) ? 0 : -1}
                    className="tab"
                    onClick={() => setActivePath(path)}
                    onKeyDown={(event) => {
                      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
                      event.preventDefault();
                      const index = openTabs.indexOf(path);
                      const next = event.key === "Home" ? 0 : event.key === "End" ? openTabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + openTabs.length) % openTabs.length;
                      setActivePath(openTabs[next]); document.getElementById(`forge-tab-${encodeURIComponent(openTabs[next])}`)?.focus();
                    }}
                  >
                    {changedFiles.includes(path) ? "● " : ""}{basename}
                    {contentErrors[`${sourceKey}:${path}`] ? <span className="editor-tab__warn" title={contentErrors[`${sourceKey}:${path}`]}>⚠</span> : null}
                  </button>
                );
              })}
            </div>
            {activePath && <button type="button" className="btn btn--quiet btn--sm" aria-label={`Close ${activePath}`} onClick={(event) => closeTab(activePath, event)}>Close file ×</button>}
          </div>
          <div className="editor-content" id="forge-editor-panel" role={activePath ? "tabpanel" : undefined} aria-labelledby={activePath ? `forge-tab-${encodeURIComponent(activePath)}` : undefined}>
            {activePath && contentError && (
              <div className="state-block state-block--error" role="alert" style={{ padding: "0.9rem" }}>
                <span className="state-mark" aria-hidden="true">×</span>
                <h3 style={{ margin: "0 0 0.3rem", fontSize: "var(--text-xs)" }}>Cannot read file</h3>
                <p style={{ margin: 0, fontSize: "var(--text-xs)" }}>{contentError}</p>
              </div>
            )}
            {compare && <div className="code-comparison"><div className="comparison-sources mono"><span>ORIGINAL REPOSITORY</span><span>FROZEN CANDIDATE</span></div>{comparisonError ? <p className="field-error" role="alert">{comparisonError}</p> : comparison ? <ForgeDiffEditor original={comparison.original} modified={comparison.modified} language={language} /> : <div className="state-block" role="status"><span className="spinner" aria-hidden="true" /><p>Reading both recorded sources…</p></div>}</div>}
            {!compare && activePath && content === undefined && !contentError && <div className="state-block code-loading" role="status"><span className="spinner" aria-hidden="true" /><p>Reading {activePath}…</p></div>}
            {!compare && activePath && content !== undefined && contentError === undefined && (
              <>
                <p className="editor-path mono" title={activePath}>{activePath}</p>
                <ForgeEditor value={content ?? ""} language={language} height="100%" line={line} />
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
          <div className="code-statusbar mono"><span>{source === "candidate" && candidateId ? "FROZEN SNAPSHOT" : "REPOSITORY SOURCE"}</span><span>{activePath ? `${language} · ${content?.split("\n").length ?? 0} lines` : "No file selected"}</span><span>READ ONLY</span></div>
        </section>
        <ResizeHandle label="Inspector width" value={railWidth} min={220} max={380} direction={-1} onChange={(next) => saveLayout(explorerWidth, next)} />

        {detail && <FileContext detail={detail} path={activePath} content={content} language={language} onEvidence={setEvidenceId} onLine={(next) => { setCompare(false); setLine(next); }} onRefresh={reload} />}
      </div>

      {candidateError && <p className="workbench-error" role="alert">{candidateError} <button onClick={reload}>Refresh mission</button></p>}
      <ActivityDock stream={events} onEvidence={setEvidenceId} />
      {paletteOpen && <CommandPalette missionId={missionId} paths={treePaths ?? detail?.repository_files ?? []} onOpenFile={openFile} onClose={() => setPaletteOpen(false)} />}
      {evidenceId && <EvidenceDetail key={evidenceId} missionId={missionId} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />}
    </div>
  );
}
