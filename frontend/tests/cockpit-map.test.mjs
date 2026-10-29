import test from "node:test";
import assert from "node:assert/strict";
import { buildMissionMap, fitCamera, zoomAt } from "../src/components/cockpit/map-model.ts";

const mission = { id: "m1", status: "PLANNING", active_candidate_id: null };
const empty = { mission, tasks: [], candidates: [], evidence: [], findings: [] };
const roles = [{ id: "SHOGUN", name: "Shogun", role: "Planner", glyph: "◇" }];

test("empty guild maps contain roles, not fabricated tasks or candidates", () => {
  const graph = buildMissionMap(empty, roles, "guild");
  assert.deepEqual(graph.nodes.map((node) => node.kind), ["mission", "agent"]);
  assert.equal(graph.nodes[1].state, "0 ASSIGNED");
  assert.equal(graph.edges[0].kind, "ownership");
  assert.equal(graph.edges[0].active, false);
});

test("task links only connect actual dependency records and follow dependency levels", () => {
  const tasks = [
    { id: "a", title: "Build", owner_agent: "SAMURAI", status: "DONE", dependencies: [] },
    { id: "b", title: "Check", owner_agent: "SENTINEL", status: "RUNNING", dependencies: ["a", "missing"] },
  ];
  const graph = buildMissionMap({ ...empty, tasks }, roles, "tasks");
  const dependencies = graph.edges.filter((edge) => edge.kind === "dependency");
  assert.equal(dependencies.length, 1);
  assert.equal(dependencies[0].from, "task:a");
  assert.equal(dependencies[0].to, "task:b");
  assert.equal(dependencies[0].active, true);
  assert.ok(graph.nodes.find((node) => node.entityId === "b").x > graph.nodes.find((node) => node.entityId === "a").x);
});

test("evidence with a missing candidate is displayed without inventing a binding", () => {
  const graph = buildMissionMap({ ...empty, evidence: [{ id: "e", kind: "BASELINE", source: "SENTINEL", candidate_id: "missing", exit_code: null }] }, roles, "evidence");
  assert.equal(graph.nodes.filter((node) => node.kind === "evidence").length, 1);
  assert.equal(graph.edges.length, 0);
});

test("camera zoom preserves the world point under the cursor and clamps extremes", () => {
  const camera = { x: 24, y: -30, zoom: .8 };
  const cursor = { x: 400, y: 250 };
  const next = zoomAt(camera, cursor, 1.4);
  assert.ok(Math.abs((cursor.x - camera.x) / camera.zoom - (cursor.x - next.x) / next.zoom) < 1e-8);
  assert.ok(Math.abs((cursor.y - camera.y) / camera.zoom - (cursor.y - next.y) / next.zoom) < 1e-8);
  assert.equal(zoomAt(camera, cursor, 30).zoom, 1.8);
  assert.equal(zoomAt(camera, cursor, .01).zoom, .35);
});

test("fit camera keeps ordinary node bounds inside the viewport", () => {
  const nodes = [{ x: 100, y: 100, width: 200, height: 100 }, { x: 900, y: 500, width: 200, height: 100 }];
  const camera = fitCamera(nodes, 1200, 800);
  for (const node of nodes) {
    assert.ok(camera.x + (node.x - node.width / 2) * camera.zoom >= 0);
    assert.ok(camera.y + (node.y - node.height / 2) * camera.zoom >= 0);
    assert.ok(camera.x + (node.x + node.width / 2) * camera.zoom <= 1200);
    assert.ok(camera.y + (node.y + node.height / 2) * camera.zoom <= 800);
  }
});
