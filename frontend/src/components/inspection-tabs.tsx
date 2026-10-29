"use client";

import { useState } from "react";

const panels = {
  Problems: "No diagnostics are available. Connect a mission to inspect real findings.",
  Tests: "No tests have run. Actual check results will appear here after execution.",
  Terminal: "No authorized command output is available. No terminal activity is simulated.",
  Diff: "No candidate or diff is available. Changes will be tied to a real candidate version.",
  Evidence: "No verification evidence or approval action is available without a real candidate.",
};
type Panel = keyof typeof panels;
const names = Object.keys(panels) as Panel[];

export function InspectionTabs() {
  const [active, setActive] = useState<Panel>("Problems");
  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>, name: Panel) {
    const current = names.indexOf(name);
    const next = event.key === "ArrowRight" ? (current + 1) % names.length : event.key === "ArrowLeft" ? (current + names.length - 1) % names.length : event.key === "Home" ? 0 : event.key === "End" ? names.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    setActive(names[next]);
    document.getElementById(`tab-${names[next]}`)?.focus();
  }
  return <section className="dojo-inspection" aria-label="Mission inspection panels"><div className="inspection-tabs" role="tablist" aria-label="Inspection panel">{names.map((name) => <button key={name} id={`tab-${name}`} type="button" role="tab" aria-selected={active === name} aria-controls="inspection-panel" tabIndex={active === name ? 0 : -1} onClick={() => setActive(name)} onKeyDown={(event) => onKeyDown(event, name)}>{name}</button>)}</div><div id="inspection-panel" role="tabpanel" tabIndex={0} aria-labelledby={`tab-${active}`}>{panels[active]}</div></section>;
}
