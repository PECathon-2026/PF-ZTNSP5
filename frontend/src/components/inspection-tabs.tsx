"use client";

import { useState } from "react";
import type { Candidate, Criterion, Evidence, Finding } from "@/lib/backend";

type Panel = "Problems" | "Tests" | "Terminal" | "Diff" | "Evidence";
const names: Panel[] = ["Problems", "Tests", "Terminal", "Diff", "Evidence"];

export function InspectionTabs({ findings = [], criteria = [], output = "", diff = "", evidence = [], candidate }: {
  findings?: Finding[]; criteria?: Criterion[]; output?: string; diff?: string; evidence?: Evidence[]; candidate?: Candidate;
}) {
  const [active, setActive] = useState<Panel>("Problems");
  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, name: Panel) {
    const current = names.indexOf(name);
    const next = event.key === "ArrowRight" ? (current + 1) % names.length : event.key === "ArrowLeft" ? (current + names.length - 1) % names.length : event.key === "Home" ? 0 : event.key === "End" ? names.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault(); setActive(names[next]); document.getElementById(`tab-${names[next]}`)?.focus();
  }
  const panels: Record<Panel, React.ReactNode> = {
    Problems: findings.length ? findings.map((item) => <p key={item.id}>{item.severity} · {item.title} ({item.status})</p>) : "No findings for this candidate.",
    Tests: criteria.length ? criteria.map((item) => <p key={item.id}>{item.status} · {item.description} {item.evidence_ids.length ? `(${item.evidence_ids.join(", ")})` : "— pending independent verification"}</p>) : "No acceptance criteria recorded.",
    Terminal: <pre>{output || "No approved check output for this candidate."}</pre>,
    Diff: <pre>{diff || "No candidate diff available."}</pre>,
    Evidence: candidate ? <><p>Candidate: {candidate.id} · {candidate.content_fingerprint}</p>{evidence.map((item) => <p key={item.id}>{item.kind} · {item.id} · {item.metadata.check_profile ?? "review/diff"} · exit {item.exit_code ?? "n/a"}</p>)}</> : "No candidate evidence available.",
  };
  return <section className="dojo-inspection" aria-label="Mission inspection panels"><div className="inspection-tabs" role="tablist" aria-label="Inspection panel">{names.map((name) => <button key={name} id={`tab-${name}`} type="button" role="tab" aria-selected={active === name} aria-controls="inspection-panel" tabIndex={active === name ? 0 : -1} onClick={() => setActive(name)} onKeyDown={(event) => onKeyDown(event, name)}>{name}</button>)}</div><div id="inspection-panel" role="tabpanel" tabIndex={0} aria-labelledby={`tab-${active}`}>{panels[active]}</div></section>;
}
