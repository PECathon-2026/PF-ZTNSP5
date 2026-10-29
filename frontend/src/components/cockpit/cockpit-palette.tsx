"use client";

import Link from "next/link";
import { useState } from "react";
import { Search, ArrowUpRight } from "lucide-react";
import { Modal } from "@/components/mission/modal";
import type { MapNode } from "./map-model";

export function CockpitPalette({ nodes, files, missionId, onSelect, onClose }: { nodes: MapNode[]; files: string[]; missionId: string; onSelect: (node: MapNode) => void; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const search = query.trim().toLowerCase();
  const results = nodes.filter((node) => `${node.title} ${node.subtitle} ${node.entityId}`.toLowerCase().includes(search)).slice(0, 20);
  const paths = search ? files.filter((file) => file.toLowerCase().includes(search)).slice(0, 15) : [];
  return <Modal title="Navigate the mission" onClose={onClose}>
    <label className="cockpit-search-label" htmlFor="cockpit-search"><Search size={17} /> Find a role, task, candidate, or file</label>
    <input id="cockpit-search" className="cockpit-search" autoFocus value={query} onChange={(event) => setQuery(event.target.value)}
      onKeyDown={(event) => { if (event.key === "ArrowDown") { event.preventDefault(); event.currentTarget.closest("dialog")?.querySelector<HTMLElement>(".cockpit-search-results button,.cockpit-search-results a")?.focus(); } }} />
    <ul className="cockpit-search-results" onKeyDown={(event) => {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      event.preventDefault(); const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLElement>("button,a"));
      const index = buttons.indexOf(document.activeElement as HTMLElement);
      buttons[(index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
    }}>{results.map((node) => <li key={node.id}><button onClick={() => { onSelect(node); onClose(); }}><span className="mono">{node.kind}</span><strong>{node.title}</strong><ArrowUpRight size={15} /></button></li>)}
      {paths.map((file) => <li key={file}><Link href={`/missions/${missionId}/forge?file=${encodeURIComponent(file)}`}><span className="mono">file</span><strong>{file}</strong><ArrowUpRight size={15} /></Link></li>)}
    </ul>
    {!results.length && !paths.length && <p role="status">No recorded entities or files match “{query}”.</p>}
    <p className="muted mono" style={{ fontSize: ".7rem" }}>↑ ↓ navigate · Enter select · Esc return to field</p>
  </Modal>;
}
