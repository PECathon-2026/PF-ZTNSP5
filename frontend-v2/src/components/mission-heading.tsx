"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Check, ChevronRight, Copy, FileText, GitBranch, MessageSquare, X } from "lucide-react";
import { missionBrief } from "@/lib/mission-brief";

export function MissionHeading({ id, repository, request }: { id: string; repository: string; request?: string }) {
  const brief = useMemo(() => missionBrief(request || ""), [request]);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("structured");
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open) dialog.current?.showModal();
    else dialog.current?.close();
  }, [open]);
  async function copy() {
    try { await navigator.clipboard.writeText(brief.fullText); setCopied(true); setCopyError(""); }
    catch { setCopyError("Copy unavailable. Select the complete text in the Original text tab."); }
  }
  return <div className="mission-heading">
    <span className="eyebrow"><GitBranch size={12}/>{repository}</span>
    <h1>{request ? brief.title : "Opening the dojo…"}</h1>
    <div className="mission-subline"><code>{id}</code>{brief.parentMissionId && <Link href={`/missions/${brief.parentMissionId}/workspace?returnTo=${id}`} className="parent-mission-link">Follow-up <ArrowUpRight size={11}/></Link>}
      {request && <button className="brief-trigger" onClick={() => { setOpen(true); setCopied(false); }}><FileText size={13}/>Mission brief{brief.exchanges.length > 0 && <span>{brief.exchanges.length} {brief.exchanges.length === 1 ? "clarification" : "clarifications"}</span>}<ChevronRight size={13}/></button>}
    </div>
    <dialog ref={dialog} className="brief-dialog" onCancel={() => setOpen(false)} onClose={() => setOpen(false)} aria-labelledby="brief-title">
      <div className="drawer-heading"><div><span className="eyebrow">THE COMPLETE CONTEXT</span><h2 id="brief-title">Mission brief</h2></div><button className="icon-button" aria-label="Close mission brief" onClick={() => setOpen(false)}><X size={18}/></button></div>
      <div className="brief-dialog-toolbar"><div className="segmented"><button className={mode === "structured" ? "selected" : ""} onClick={() => setMode("structured")}>Overview</button><button className={mode === "raw" ? "selected" : ""} onClick={() => setMode("raw")}>Original text</button></div><button className="button small" onClick={copy}>{copied ? <Check size={13}/> : <Copy size={13}/>}<span aria-live="polite">{copied ? "Copied" : "Copy full brief"}</span></button></div>
      {copyError && <p role="status" className="error-banner">{copyError}</p>}
      <div className="brief-dialog-body">{mode === "raw" ? <pre className="brief-full-text">{brief.fullText}</pre> : <>
        {brief.parentMissionId && <div className="brief-parent"><GitBranch size={15}/><div><span>Continues the discussion from</span><Link href={`/missions/${brief.parentMissionId}/workspace?returnTo=${id}`}>{brief.parentMissionId} <ArrowUpRight size={12}/></Link></div></div>}
        <section className="brief-section"><span className="eyebrow">01 / ORIGINAL REQUEST</span><p>{brief.originalRequest}</p></section>
        {brief.instructions && <section className="brief-section brief-instructions"><span className="eyebrow">02 / FOLLOW-UP INSTRUCTIONS</span><p>{brief.instructions}</p></section>}
        {brief.exchanges.length > 0 && <section className="brief-section"><span className="eyebrow"><MessageSquare size={12}/> EARLIER CLARIFICATIONS</span><div className="brief-exchanges">{brief.exchanges.map((exchange, index) => <details key={index} className="brief-exchange"><summary><span className="exchange-number">{String(index + 1).padStart(2, "0")}</span><span>{exchange.answer || "View clarification"}</span><ChevronRight size={14}/></summary><div><h3>Question</h3><p>{exchange.question}</p>{exchange.answer && <><h3>Your answer</h3><p className="brief-answer">{exchange.answer}</p></>}</div></details>)}</div></section>}
        <p className="brief-note">Display formatting only. The original request remains unchanged and is available in the Original text tab.</p>
      </>}</div>
    </dialog>
  </div>;
}
