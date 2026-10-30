"use client";

import { useEffect, useMemo, useState } from "react";
import { Background, BackgroundVariant, Controls, Handle, MarkerType, Position, ReactFlow, useNodesState, type NodeProps, type Node, type Edge, type ReactFlowInstance } from "@xyflow/react";
import { ArrowRight, ChevronRight, MessageSquare, X } from "lucide-react";
import "@xyflow/react/dist/style.css";
import { agents, agentStatus, graphLinks } from "@/lib/mission";
import { AgentArt } from "./agent-art";
import { Empty } from "./ui";
import type { Agent, Detail, MissionEvent } from "@/lib/types";

type AgentNode = Node<{ agent: Agent; state: string; task: string; selected: boolean }, "agent">;
function AgentNodeView({ data }: NodeProps<AgentNode>) {
  const person = agents.find(a => a.id === data.agent)!;
  return <div className={`graph-agent ${data.selected ? "selected" : ""}`} style={{ "--agent-color": person.color } as React.CSSProperties}>
    <Handle type="target" position={Position.Top}/><div className="graph-agent-heading"><span className="eyebrow">{person.role}</span><span className={`agent-state ${data.state}`}>{data.state}</span></div><AgentArt agent={person.id} active={data.state === "working"}/><h3>{person.name}</h3><p>{data.task}</p><Handle type="source" position={Position.Bottom}/>
  </div>;
}
const nodeTypes = { agent: AgentNodeView };
const name = (role: string) => agents.find(a => a.id === role)?.name || role;

export default function AgentGraph({ detail, events, selected, onSelect, connected = true, candidateId, onEvidence, onInspectConnection, onCandidate }: {
  detail: Detail; events: MissionEvent[]; selected: Agent | null; onSelect: (agent: Agent) => void; connected?: boolean;
  candidateId: string; onEvidence: (id: string) => void; onInspectConnection: () => void; onCandidate: (id: string) => void;
}) {
  const [scope, setScope] = useState("mission");
  const [inspected, setInspected] = useState<string | null>(null);
  const [showMessages, setShowMessages] = useState(false);
  const [flow, setFlow] = useState<ReactFlowInstance | null>(null);
  const descriptors: Node[] = useMemo(() => agents.map((agent, i) => ({
    id: agent.id, type: "agent", position: [{ x: 230, y: 0 }, { x: 0, y: 300 }, { x: 460, y: 300 }, { x: 230, y: 610 }][i],
    data: { agent: agent.id, state: connected ? agentStatus(agent.id, detail, events) : "offline", selected: selected === agent.id,
      task: detail.tasks.find(t => t.owner_agent === agent.id && t.status === "RUNNING")?.title || events.filter(e => e.source === agent.id).at(-1)?.display_payload.summary || "Awaiting recorded activity" },
    ariaLabel: `${agent.name}, ${agent.role}. Open agent details`,
  })), [detail, events, selected, connected]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(descriptors);
  useEffect(() => {
    setNodes(old => descriptors.map(n => ({ ...n, position: old.find(o => o.id === n.id)?.position || n.position })));
  }, [descriptors, setNodes]);
  useEffect(() => {
    const timer = setTimeout(() => flow?.fitView({ padding: 0.18, duration: 0 }), 80);
    return () => clearTimeout(timer);
  }, [flow, selected]);
  const links = graphLinks(detail, scope === "candidate" ? candidateId : undefined);
  const current = links.find(l => l.id === inspected);
  const messages = detail.messages.filter(m => current?.messageIds.includes(m.id));
  const edges: Edge[] = links.map(link => ({ id: link.id, source: link.source, target: link.target,
    label: `${link.label}${link.count > 1 ? ` ×${link.count}` : ""}`, type: "smoothstep", animated: false,
    selected: inspected === link.id, interactionWidth: 30,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#b8b496" },
    style: { stroke: inspected === link.id ? "#e8ca83" : link.label.includes("finding") || link.label.includes("blocker") ? "#e6806d" : "#a3ab95", strokeWidth: inspected === link.id ? 2.5 : 1.4 },
    labelStyle: { fill: "#c7c7b7", fontSize: 11 }, labelBgStyle: { fill: "#151e20" },
  }));
  function inspect(id: string) { setInspected(id); setShowMessages(true); onInspectConnection(); }
  return <div className="graph-canvas">
    <div className="graph-caption"><span className="eyebrow">GUILD TOPOLOGY</span><p>Select an agent or a recorded connection.</p><small>Nodes show the latest mission state; edges can be filtered by candidate.</small>
      <div className="graph-actions"><select aria-label="Graph connection scope" value={scope} onChange={e => { setScope(e.target.value); setInspected(null); }}><option value="mission">All mission connections</option><option value="candidate">Selected candidate connections</option></select><button className="button small" onClick={() => { setShowMessages(v => !v); onInspectConnection(); }}><MessageSquare size={13}/>{links.length} connections</button></div>
    </div>
    <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onInit={setFlow}
      onNodeClick={(_, node) => { setShowMessages(false); onSelect(node.id as Agent); }} onEdgeClick={(_, edge) => inspect(edge.id)}
      fitView fitViewOptions={{ padding: 0.18 }} minZoom={0.25} maxZoom={1.5} nodesDraggable nodesConnectable={false} colorMode="dark">
      <Background variant={BackgroundVariant.Dots} color="#42524b" gap={24} size={1}/><Controls showInteractive={false}/>
    </ReactFlow>
    {showMessages && <aside className="connection-drawer" aria-label="Connection details"><div className="drawer-heading"><h3>{current ? "Recorded handoff" : "Mission connections"}</h3><button className="icon-button" aria-label="Close connection details" onClick={() => { setShowMessages(false); setInspected(null); }}><X size={16}/></button></div><div className="connection-content">
      {!links.length && <Empty title="No recorded connections in this scope"/>}
      <div className="connection-list">{links.map(link => <button key={link.id} className={current?.id === link.id ? "selected" : ""} onClick={() => inspect(link.id)}><span>{name(link.source)} <ArrowRight size={12}/> {name(link.target)}</span><small>{link.label} · {link.count} recorded</small></button>)}</div>
      {messages.map(message => <article className="message-record" key={message.id}><span className="eyebrow">{message.type}</span><p>{message.summary}</p><code>{message.id}</code>{message.candidate_id && <button className="text-link" onClick={() => onCandidate(message.candidate_id!)}>Select {message.candidate_id}<ChevronRight size={12}/></button>}<div className="inline-links">{message.evidence_ids.map(id => <button key={id} onClick={() => onEvidence(id)}>Inspect evidence <ChevronRight size={12}/></button>)}</div></article>)}
    </div></aside>}
    <div className="graph-checkpoint"><span>System checkpoint</span><strong>{detail.mission.status === "APPLIED" ? "Approved change applied" : detail.mission.status === "VERIFIED_AWAITING_APPROVAL" ? "Verified · human decision required" : "Verification and human approval remain separate"}</strong></div>
  </div>;
}
