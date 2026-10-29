"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api, activeCandidate, approvedCandidate, checkedCandidate, sequenceUpdate, terminalStatuses, type MissionDetail, type MissionEvent } from "@/lib/backend";
import { InspectionTabs } from "@/components/inspection-tabs";

export function MissionDojo() {
  const missionId = useSearchParams().get("mission");
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [file, setFile] = useState("");
  const [content, setContent] = useState("");
  const [diff, setDiff] = useState("");
  const [output, setOutput] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const cursor = useRef(0);
  const active = detail ? activeCandidate(detail) : undefined;
  const candidateId = active?.id;

  const refresh = useCallback(async () => {
    if (!missionId) return;
    try { setDetail(await api<MissionDetail>(`/api/missions/${encodeURIComponent(missionId)}`)); setError(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Could not load mission"); }
  }, [missionId]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!missionId) return;
    let closed = false;
    let source: EventSource | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failures = 0;
    const open = () => {
      if (closed) return;
      source = new EventSource(`/api/missions/${encodeURIComponent(missionId)}/events?after=${cursor.current}`);
      source.addEventListener("mission", (message) => {
        let event: MissionEvent;
        try { event = JSON.parse((message as MessageEvent).data) as MissionEvent; }
        catch { void refresh(); return; }
        if (event.mission_id !== missionId) return;
        const order = sequenceUpdate(cursor.current, event.sequence);
        if (order === "duplicate") return;
        if (order === "gap") { setEvents([]); void refresh(); }
        cursor.current = event.sequence;
        failures = 0;
        setEvents((current) => [...current.slice(-99), event]);
        void refresh();
        if (terminalStatuses.has(String(event.display_payload?.status))) source?.close();
      });
      source.onerror = () => {
        source?.close();
        if (closed) return;
        void refresh();
        failures += 1;
        timer = setTimeout(open, Math.min(1000 * 2 ** Math.min(failures, 4), 15000));
      };
    };
    open();
    return () => { closed = true; source?.close(); if (timer) clearTimeout(timer); };
  }, [missionId, refresh]);

  useEffect(() => {
    if (!missionId || !file || !detail) return;
    const controller = new AbortController();
    const location = candidateId
      ? `/api/missions/${encodeURIComponent(missionId)}/candidates/${encodeURIComponent(candidateId)}/file?path=${encodeURIComponent(file)}`
      : `/api/repositories/${encodeURIComponent(detail.mission.repository_id)}/file?path=${encodeURIComponent(file)}`;
    api<{ content: string }>(location, { signal: controller.signal }).then((value) => setContent(value.content)).catch(() => { if (!controller.signal.aborted) setContent("File unavailable"); });
    return () => controller.abort();
  }, [missionId, file, candidateId, detail?.mission.repository_id, detail?.mission.status]);

  useEffect(() => {
    if (!missionId || !candidateId) { setDiff(""); return; }
    const controller = new AbortController();
    api<{ unified_diff: string }>(`/api/missions/${encodeURIComponent(missionId)}/candidates/${encodeURIComponent(candidateId)}/diff`, { signal: controller.signal })
      .then((value) => setDiff(value.unified_diff)).catch(() => { if (!controller.signal.aborted) setDiff("Diff unavailable"); });
    return () => controller.abort();
  }, [missionId, candidateId]);

  const check = detail?.evidence.find((item) => item.candidate_id === candidateId && item.metadata.check_profile);
  useEffect(() => {
    if (!missionId || !check) { setOutput(""); return; }
    const controller = new AbortController();
    api<{ stdout: string; stderr: string }>(`/api/missions/${encodeURIComponent(missionId)}/evidence/${encodeURIComponent(check.id)}`, { signal: controller.signal })
      .then((item) => setOutput([item.stdout, item.stderr].filter(Boolean).join("\n"))).catch(() => { if (!controller.signal.aborted) setOutput("Check output unavailable"); });
    return () => controller.abort();
  }, [missionId, check?.id]);

  async function action(route: string, body?: object) {
    if (!missionId) return;
    setBusy(true); setError("");
    try {
      await api(`/api/missions/${encodeURIComponent(missionId)}/${route}`, { method: "POST", ...(body ? { body: JSON.stringify(body) } : {}) });
      await refresh();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Action failed"); }
    finally { setBusy(false); }
  }

  if (!missionId) return <div className="interior-page dojo-page"><h1>Engineering workspace</h1><p>Open a mission from setup to inspect its real state.</p><Link href="/setup" className="outline-button">Prepare mission ↗</Link></div>;
  if (!detail) return <div className="interior-page dojo-page" role="status">{error || "Loading mission…"}</div>;

  const { mission } = detail;
  const question = detail.clarifications.find((item) => item.status === "OPEN");
  const approved = approvedCandidate(detail);
  const tested = checkedCandidate(detail);
  return <div className="interior-page dojo-page">
    <header className="dojo-heading"><div><p className="eyebrow">THE DOJO / {mission.status} · PLAN REVISION {detail.plan_revision}</p><h1>Engineering workspace</h1><p>{mission.request_text}</p><p>Repair rounds: {mission.budgets.repair_rounds_used}/{mission.budgets.max_repair_rounds}{mission.failure_reason && ` · ${mission.failure_reason}`}</p></div><Link className="outline-button" href="/setup">New mission ↗</Link></header>
    {error && <p role="alert" className="dojo-warning">{error}</p>}
    <div className="dojo-controls">
      {mission.status === "READY_FOR_AUTHORIZATION" && <button className="outline-button" disabled={busy} onClick={() => action("authorize", { scope_version: mission.scope_version })}>Authorize planned workspace work</button>}
      {question && <form onSubmit={(event) => { event.preventDefault(); void action("clarifications", { question_id: question.id, answer: answer.trim() }); setAnswer(""); }}><label htmlFor="clarification-answer">Shogun asks: {question.question}</label><input id="clarification-answer" value={answer} onChange={(event) => setAnswer(event.target.value)} /><button className="outline-button" disabled={busy || !answer.trim()}>Answer</button></form>}
      {mission.status === "VERIFYING" && <button className="outline-button" disabled={busy} onClick={() => action("verify")}>Run independent verification</button>}
      {mission.status === "VERIFIED_AWAITING_APPROVAL" && active && !approved && <><p>Review the diff before deciding. Candidate fingerprint: <code>{active.content_fingerprint}</code></p><button className="outline-button" disabled={busy} onClick={() => action("approve", { candidate_id: active.id, candidate_fingerprint: active.content_fingerprint, decision: "APPROVED" })}>Approve exact candidate</button><button className="outline-button" disabled={busy} onClick={() => action("approve", { candidate_id: active.id, candidate_fingerprint: active.content_fingerprint, decision: "REJECTED" })}>Reject candidate</button></>}
      {mission.status === "VERIFIED_AWAITING_APPROVAL" && approved && active && <button className="outline-button" disabled={busy} onClick={() => action("apply", { candidate_id: active.id })}>Apply approved candidate to original</button>}
      {!terminalStatuses.has(mission.status) && <button className="outline-button" disabled={busy} onClick={() => action("cancel")}>Cancel mission</button>}
    </div>
    <div className="dojo-frame"><aside className="dojo-explorer"><div className="pane-heading">REPOSITORY EXPLORER <span>{detail.repository_files.length} files</span></div><div className="pane-empty">{detail.repository_files.map((name) => <button className="dojo-file" type="button" key={name} onClick={() => setFile(name)} aria-pressed={file === name}>{name}</button>)}</div></aside><section className="dojo-editor"><div className="pane-heading">EDITOR <span>{file || "NO FILE OPEN"}</span></div><pre className="dojo-code">{file ? content : "Select a source file to inspect the current candidate."}</pre></section><aside className="dojo-activity"><div className="pane-heading">GUILD ACTIVITY <span>{events.length} live events</span></div><div className="pane-empty"><p>Status: {mission.status}</p><p>Tests: {tested ? "Passed for current candidate" : "Not confirmed for current candidate"}</p><p>Approval: {approved ? "Recorded for current candidate" : "Not recorded"}</p>{detail.tasks.map((task) => <p key={task.id}>{task.owner_agent}: {task.title} · {task.status} (attempt {task.attempt})</p>)}{events.slice(-12).map((item) => <p key={item.sequence}>{item.sequence} · {item.event_type}</p>)}</div></aside><InspectionTabs findings={detail.findings.filter((item) => item.candidate_id === candidateId)} criteria={detail.criteria} output={output} diff={diff} evidence={detail.evidence.filter((item) => item.candidate_id === candidateId)} candidate={active} /></div>
    <p className="dojo-warning">Evidence and approval are specific to this candidate. A new edit invalidates previous badges. The original repository changes only after explicit approval and apply.</p>
  </div>;
}
