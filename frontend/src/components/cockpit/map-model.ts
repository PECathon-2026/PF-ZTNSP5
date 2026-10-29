import type { MissionDetail } from "@/lib/types";

export type Lens = "guild" | "tasks" | "evidence";
export type NodeKind = "mission" | "agent" | "task" | "candidate" | "evidence" | "finding";
export type Point = { x: number; y: number };
export type Camera = Point & { zoom: number };
export type MapNode = Point & { id: string; entityId: string; kind: NodeKind; title: string; subtitle: string; state: string; glyph: string; width: number; height: number };
export type MapEdge = { id: string; from: string; to: string; kind: "ownership" | "dependency" | "binding"; active: boolean };
export type Role = { id: string; name: string; role: string; glyph: string };
export type MissionMapModel = { nodes: MapNode[]; edges: MapEdge[] };

export const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));
export const nodeId = (kind: NodeKind, id: string) => `${kind}:${id}`;

export function zoomAt(camera: Camera, cursor: Point, nextZoom: number): Camera {
  const zoom = clamp(nextZoom, .35, 1.8);
  return { zoom, x: cursor.x - (cursor.x - camera.x) * zoom / camera.zoom, y: cursor.y - (cursor.y - camera.y) * zoom / camera.zoom };
}

export function fitCamera(nodes: MapNode[], width: number, height: number): Camera {
  if (!nodes.length || width <= 0 || height <= 0) return { x: 0, y: 0, zoom: 1 };
  const left = Math.min(...nodes.map((node) => node.x - node.width / 2));
  const right = Math.max(...nodes.map((node) => node.x + node.width / 2));
  const top = Math.min(...nodes.map((node) => node.y - node.height / 2));
  const bottom = Math.max(...nodes.map((node) => node.y + node.height / 2));
  const zoom = clamp(Math.min((width - 120) / Math.max(right - left, 1), (height - 170) / Math.max(bottom - top, 1)), .35, 1.05);
  return { zoom, x: width / 2 - (left + right) / 2 * zoom, y: height / 2 - (top + bottom) / 2 * zoom + 15 };
}

export function buildMissionMap(detail: MissionDetail, roles: readonly Role[], lens: Lens): MissionMapModel {
  const nodes: MapNode[] = [];
  const edges: MapEdge[] = [];
  function add(kind: NodeKind, entityId: string, title: string, subtitle: string, state: string, glyph: string, x: number, y: number) {
    nodes.push({ id: nodeId(kind, entityId), entityId, kind, title, subtitle, state, glyph, x, y, width: kind === "mission" ? 180 : 210, height: kind === "mission" ? 180 : 108 });
  }
  function connect(from: string, to: string, kind: MapEdge["kind"], active = false) {
    edges.push({ id: `${from}>${to}`, from, to, kind, active });
  }
  const mission = detail.mission;
  const root = nodeId("mission", mission.id);
  add("mission", mission.id, "KAGE", "MISSION CORE", mission.status, "影", 720, 470);
  if (lens === "guild" || (lens === "tasks" && !detail.tasks.length)) {
    const positions = [[310, 230], [1130, 260], [1130, 700], [310, 730]];
    roles.forEach((role, index) => {
      const owned = detail.tasks.filter((task) => task.owner_agent === role.id);
      const running = owned.filter((task) => task.status === "RUNNING").length;
      const [x, y] = positions[index % positions.length];
      add("agent", role.id, role.name, role.role, running ? `${running} RUNNING` : `${owned.length} ASSIGNED`, role.glyph, x, y);
      connect(root, nodeId("agent", role.id), "ownership", running > 0);
    });
    const candidate = detail.candidates.find((item) => item.id === mission.active_candidate_id);
    if (candidate) {
      add("candidate", candidate.id, "Frozen candidate", `${candidate.changed_files.length} changed files`, candidate.ui_badge, "◈", 720, 820);
      connect(root, nodeId("candidate", candidate.id), "binding");
    }
  } else if (lens === "tasks") {
    const tasks = detail.tasks;
    const levels = new Map<string, number>();
    function level(id: string, visiting = new Set<string>()): number {
      if (levels.has(id)) return levels.get(id)!;
      if (visiting.has(id)) return 0;
      const task = tasks.find((item) => item.id === id);
      if (!task) return 0;
      const dependencies = task.dependencies.filter((dep) => tasks.some((item) => item.id === dep));
      const next = new Set(visiting).add(id);
      const result = dependencies.length ? Math.max(...dependencies.map((dep) => level(dep, next))) + 1 : 0;
      levels.set(id, result); return result;
    }
    const rows = new Map<number, number>();
    nodes[0].x = 150; nodes[0].y = 420;
    tasks.forEach((task) => {
      const column = level(task.id); const row = rows.get(column) ?? 0;
      rows.set(column, row + 1);
      add("task", task.id, task.title, task.owner_agent, task.status, task.status === "DONE" ? "✓" : "◇", 430 + column * 290, 200 + row * 165);
      if (!task.dependencies.length) connect(root, nodeId("task", task.id), "ownership", task.status === "RUNNING");
      task.dependencies.filter((dep) => tasks.some((item) => item.id === dep)).forEach((dep) => connect(nodeId("task", dep), nodeId("task", task.id), "dependency", task.status === "RUNNING"));
    });
  } else {
    nodes[0].x = 720; nodes[0].y = 140;
    detail.candidates.forEach((candidate, index) => {
      add("candidate", candidate.id, candidate.id, `${candidate.changed_files.length} changed files`, candidate.ui_badge, "◈", 250 + index * 265, 370);
      connect(root, nodeId("candidate", candidate.id), "binding");
    });
    detail.evidence.slice(-60).forEach((record, index) => {
      add("evidence", record.id, record.kind, record.source, record.exit_code === null ? "RECORDED" : `EXIT ${record.exit_code}`, "◎", 250 + (index % 5) * 265, 620 + Math.floor(index / 5) * 155);
      if (detail.candidates.some((candidate) => candidate.id === record.candidate_id)) connect(nodeId("candidate", record.candidate_id), nodeId("evidence", record.id), "binding");
    });
    detail.findings.slice(-20).forEach((finding, index) => {
      add("finding", finding.id, finding.title, finding.source_agent, finding.severity, "!", 1700 + (index % 2) * 265, 370 + Math.floor(index / 2) * 155);
      if (finding.candidate_id && detail.candidates.some((candidate) => candidate.id === finding.candidate_id)) connect(nodeId("candidate", finding.candidate_id), nodeId("finding", finding.id), "binding");
    });
  }
  return { nodes, edges };
}
