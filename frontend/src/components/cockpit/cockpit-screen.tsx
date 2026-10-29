"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Crown, Swords, ShieldCheck, ScanEye, Search, ArrowUpRight, PanelRightOpen, Maximize2, Minimize2, ArrowLeft, Settings2 } from "lucide-react";
import { api } from "@/lib/api";
import { GUILD, missionMeta } from "@/lib/status";
import { useMissionDetail, useMissionEvents } from "@/lib/use-missions";
import { briefFromMission, useMissionBriefSync } from "@/components/shell/mission-context";
import { EvidenceDetail } from "@/components/mission/evidence-detail";
import { Modal } from "@/components/mission/modal";
import { ResizeHandle } from "@/components/forge/resize-handle";
import { buildMissionMap, nodeId, type Lens, type MapNode, type NodeKind } from "./map-model";
import { MissionMap } from "./mission-map";
import { ContextInspector, type Selection } from "./context-inspector";
import { ActivityDock } from "./activity-dock";
import { CockpitPalette } from "./cockpit-palette";
import "./cockpit.css";

const ROLE_ICONS = [Crown, Swords, ShieldCheck, ScanEye];
const LENSES = [{ id: "guild", label: "Guild field" }, { id: "tasks", label: "Task topology" }, { id: "evidence", label: "Evidence map" }] as const;

export function MissionCockpit({ missionId }: { missionId: string }) {
  const state = useMissionDetail(missionId);
  const { detail, mission, reload } = state;
  const stream = useMissionEvents(missionId, Boolean(mission) && !state.notFound, reload);
  const [lens, setLens] = useState<Lens>("guild");
  const [selection, setSelection] = useState<Selection>({ kind: "mission", entityId: missionId });
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectorWidth, setInspectorWidth] = useState(310);
  const [tab, setTab] = useState<"inspect" | "controls">("inspect");
  const [focusRequest, setFocusRequest] = useState<{ id: string; sequence: number } | null>(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const brief = useMemo(() => mission ? briefFromMission(mission) : null, [mission]);
  useMissionBriefSync(brief);
  const model = useMemo(() => detail ? buildMissionMap(detail, GUILD, lens) : { nodes: [], edges: [] }, [detail, lens]);
  const searchableNodes = useMemo(() => {
    if (!detail) return [];
    return Array.from(new Map((["guild", "tasks", "evidence"] as Lens[]).flatMap((view) => buildMissionMap(detail, GUILD, view).nodes).map((node) => [node.id, node])).values());
  }, [detail]);

  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPaletteOpen((open) => !open); }
      else if (event.key.toLowerCase() === "f" && !(event.target as HTMLElement).closest("input,textarea,select,[contenteditable=true]")) { event.preventDefault(); setInspectorOpen((open) => !open); }
    }
    window.addEventListener("keydown", shortcut);
    const initial = new URLSearchParams(window.location.search).get("lens");
    if (initial === "tasks" || initial === "evidence" || initial === "guild") setLens(initial);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  function changeLens(next: Lens) {
    setLens(next);
    const url = new URL(window.location.href); url.searchParams.set("lens", next); window.history.replaceState(null, "", url);
  }
  function selectEntity(kind: NodeKind, id: string, focus = true) {
    if (kind === "task") changeLens("tasks");
    else if (kind === "evidence" || kind === "finding") changeLens("evidence");
    else if (kind === "agent") changeLens("guild");
    setSelection({ kind, entityId: id }); setInspectorOpen(true); setTab("inspect");
    if (focus) setFocusRequest((previous) => ({ id: nodeId(kind, id), sequence: (previous?.sequence ?? 0) + 1 }));
  }
  function selectNode(node: MapNode) { selectEntity(node.kind, node.entityId, false); }
  async function cancel() {
    setCancelling(true); setCancelError(null);
    try { await api.cancelMission(missionId); setCancelOpen(false); }
    catch (error) { setCancelError(error instanceof Error ? error.message : "Cancellation could not be recorded."); }
    finally { setCancelling(false); reload(); }
  }
  if (!mission || !detail || state.notFound) return <div className="cockpit-unavailable">
    <span className="unavailable-seal" aria-hidden="true">影</span><p className="mono">KAGE / COMMAND CHAMBER</p>
    <h1>{state.notFound ? "Mission not found" : state.loading ? "Opening the field" : "Mission could not be read"}</h1>
    <p role={state.error ? "alert" : "status"}>{state.notFound ? `No mission is recorded as ${missionId}.` : state.error ?? "Reading the mission and its recorded work…"}</p>
    <div className="mission-actions"><Link href="/missions" className="btn btn--ghost">Back to missions</Link>{state.error && <button className="btn btn--primary" onClick={reload}>Retry connection</button>}</div>
  </div>;
  const meta = missionMeta(mission.status);
  const cancelAllowed = !["APPLIED", "REJECTED", "CANCELLED", "CANCEL_REQUESTED", "BLOCKED", "BUDGET_EXHAUSTED", "INTERRUPTED"].includes(mission.status);

  return <div className="mission-cockpit">
    <header className="cockpit-toolbar"><div className="cockpit-mission-id"><Link href="/missions" className="cockpit-icon-button" aria-label="Back to missions"><ArrowLeft size={17} /></Link><div><span className="mono">COMMAND CHAMBER</span><h1>{mission.id}</h1></div><span className="status" data-tone={meta.tone}>{meta.label}</span></div>
      <div className="cockpit-toolbar-actions"><button className="cockpit-search-trigger" onClick={() => setPaletteOpen(true)}><Search size={15} /><span>Find in mission</span><kbd>⌘ K</kbd></button>
        <button className="cockpit-icon-button" aria-label={inspectorOpen ? "Focus mission map" : "Restore inspector"} onClick={() => setInspectorOpen((open) => !open)}>{inspectorOpen ? <Maximize2 size={16} /> : <PanelRightOpen size={16} />}</button>
        <button className="btn btn--ghost btn--sm" onClick={() => { setInspectorOpen(true); setTab("controls"); }}><Settings2 size={14} /> Mission controls</button>
        <Link className="btn btn--primary btn--sm" href={`/missions/${missionId}/forge`}>Open forge <ArrowUpRight size={14} /></Link>
      </div>
    </header>
    <div className={`cockpit-main${inspectorOpen ? "" : " is-focused"}`} style={{ gridTemplateColumns: inspectorOpen ? `82px minmax(0,1fr) 6px ${inspectorWidth}px` : "82px minmax(0,1fr)" }}>
      <nav className="cockpit-guild-rail" aria-label="Guild roles"><span className="mono rail-heading">GUILD</span>
        {GUILD.map((role, index) => { const Icon = ROLE_ICONS[index]; const owned = detail.tasks.filter((item) => item.owner_agent === role.id);
          return <button key={role.id} className={selection.entityId === role.id ? "is-selected" : ""} aria-label={`Inspect ${role.name}`} aria-pressed={selection.entityId === role.id} onClick={() => selectEntity("agent", role.id)}><span className="rail-icon"><Icon size={20} /></span><strong>{role.name === "SHADOW COUNCIL" ? "COUNCIL" : role.name}</strong><span>{owned.length} tasks</span></button>;
        })}
        <div className="rail-bottom"><button aria-label="Inspect mission core" onClick={() => selectEntity("mission", mission.id)}><span className="rail-core" aria-hidden="true">影</span><strong>CORE</strong></button>{cancelAllowed && <button className="rail-cancel" onClick={() => setCancelOpen(true)}>Cancel mission</button>}</div>
      </nav>
      <section className="cockpit-stage" aria-label="Mission field workspace">
        <div className="field-topbar"><div className="field-title"><span className="mono">{lens === "guild" ? "GUILD COMPOSITION" : lens === "tasks" ? "DEPENDENCY TOPOLOGY" : "PROOF & PROVENANCE"}</span><h2>{lens === "guild" ? "The mission field" : lens === "tasks" ? "Work, connected." : "Follow the evidence."}</h2></div>
          <div className="field-lenses" role="tablist" aria-label="Map lens">{LENSES.map((view, index) => <button key={view.id} role="tab" id={`map-tab-${view.id}`} aria-selected={lens === view.id} tabIndex={lens === view.id ? 0 : -1} aria-controls="map-lens-panel" onClick={() => changeLens(view.id)} onKeyDown={(event) => {
            if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
            event.preventDefault(); const next = (index + (event.key === "ArrowRight" ? 1 : -1) + 3) % 3; changeLens(LENSES[next].id); document.getElementById(`map-tab-${LENSES[next].id}`)?.focus();
          }}>{view.label}</button>)}</div>
        </div>
        <div className="map-lens-panel" id="map-lens-panel" role="tabpanel" aria-labelledby={`map-tab-${lens}`}>
          <MissionMap key={lens} model={model} selectedId={nodeId(selection.kind, selection.entityId)} onSelect={selectNode} focusRequest={focusRequest} />
        </div>
        <div className="field-summary mono"><span><i />{detail.tasks.filter((item) => item.status === "RUNNING").length} running</span><span>{detail.tasks.length} tasks</span><span>{detail.evidence.length} evidence</span><span>scope {mission.scope_version}</span></div>
        {(lens === "tasks" && !detail.tasks.length) && <div className="field-empty-note"><span className="mono">PLAN NOT RECORDED</span><p>Explore the guild while the mission awaits a task plan.</p></div>}
        {(lens === "evidence" && !detail.evidence.length && !detail.candidates.length) && <div className="field-empty-note"><span className="mono">PROOF STARTS WITH A CANDIDATE</span><p>Recorded snapshots, checks, and findings will connect here.</p></div>}
        {state.error && <p className="field-refresh-error" role="alert">{state.error} <button onClick={reload}>Retry</button></p>}
      </section>
      {inspectorOpen && <><ResizeHandle label="Contextual inspector width" value={inspectorWidth} min={270} max={420} direction={-1} onChange={setInspectorWidth} />
        <ContextInspector detail={detail} selection={selection} tab={tab} onTab={setTab} onClose={() => setInspectorOpen(false)} onChange={reload} onSelect={selectEntity} onEvidence={setEvidenceId} /></>}
    </div>
    <ActivityDock stream={stream} onEvidence={setEvidenceId} />
    {paletteOpen && <CockpitPalette nodes={searchableNodes} files={detail.repository_files} missionId={missionId} onSelect={(node) => selectEntity(node.kind, node.entityId)} onClose={() => setPaletteOpen(false)} />}
    {evidenceId && <EvidenceDetail key={evidenceId} missionId={missionId} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />}
    {cancelOpen && <Modal title="Cancel this mission?" onClose={() => { if (!cancelling) setCancelOpen(false); }}><p>Cancel {missionId}. Recorded tasks and evidence remain available, but this mission cannot be resumed.</p>{cancelError && <p role="alert" className="field-error">{cancelError}</p>}<div className="dialog-actions"><button className="btn btn--ghost" disabled={cancelling} onClick={() => setCancelOpen(false)}>Keep mission</button><button className="btn btn--danger" disabled={cancelling} onClick={() => void cancel()}>{cancelling ? "Cancelling…" : "Cancel mission"}</button></div></Modal>}
  </div>;
}
