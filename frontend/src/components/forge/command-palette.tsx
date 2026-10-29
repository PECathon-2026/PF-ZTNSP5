"use client";

import Link from "next/link";
import { useState } from "react";
import { Modal } from "@/components/mission/modal";

export function CommandPalette({ missionId, paths, onOpenFile, onClose }: { missionId: string; paths: string[]; onOpenFile: (path: string) => void; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const files = paths.filter((path) => path.toLowerCase().includes(query.toLowerCase())).slice(0, 40);
  return <Modal title="Command palette" onClose={onClose}>
    <label htmlFor="palette-search">Find a file or mission destination</label>
    <input autoFocus id="palette-search" className="palette-search" value={query} onChange={(event) => setQuery(event.target.value)}
      onKeyDown={(event) => { if (event.key === "ArrowDown") { event.preventDefault(); event.currentTarget.closest("dialog")?.querySelector<HTMLElement>(".palette-results a,.palette-results button")?.focus(); } }} />
    <ul className="palette-results" onKeyDown={(event) => {
      if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
      event.preventDefault();
      const controls = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("a,button"));
      const index = controls.indexOf(document.activeElement as HTMLElement);
      controls[(index + (event.key === "ArrowDown" ? 1 : -1) + controls.length) % controls.length]?.focus();
    }}>
      {!query && <><li><Link href={`/missions/${missionId}`}>◇ Command center</Link></li><li><Link href={`/missions/${missionId}/evidence`}>核 Evidence &amp; approval</Link></li><li><Link href="/setup">＋ New mission</Link></li></>}
      {files.map((path) => <li key={path}><button type="button" onClick={() => { onOpenFile(path); onClose(); }}>{path}</button></li>)}
    </ul>
    {query && !files.length && <p role="status">No repository files match “{query}”.</p>}
    <p className="muted">↑ ↓ navigate · Enter open · Esc close · Ctrl/Cmd K toggle</p>
  </Modal>;
}
