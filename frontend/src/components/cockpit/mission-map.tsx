"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import { Crosshair, Minus, Plus, Maximize2, Move } from "lucide-react";
import { fitCamera, zoomAt, type Camera, type MapNode, type MissionMapModel, type Point } from "./map-model";

type Props = { model: MissionMapModel; selectedId: string; onSelect: (node: MapNode) => void; focusRequest: { id: string; sequence: number } | null };
type Gesture = { type: "pan" | "node"; pointer: number; start: Point; origin: Point; nodeId?: string; zoom: number };

export function MissionMap({ model, selectedId, onSelect, focusRequest }: Props) {
  const field = useRef<HTMLDivElement>(null);
  const [camera, setCamera] = useState<Camera>({ x: 0, y: 0, zoom: .7 });
  const [offsets, setOffsets] = useState<Record<string, Point>>({});
  const [dragging, setDragging] = useState(false);
  const gesture = useRef<Gesture | null>(null);
  const suppressedClick = useRef(false);
  const currentNodes = useRef(model.nodes);
  currentNodes.current = model.nodes.map((node) => ({ ...node, x: node.x + (offsets[node.id]?.x ?? 0), y: node.y + (offsets[node.id]?.y ?? 0) }));
  const signature = model.nodes.map((node) => node.id).join("|");

  function fit() {
    const bounds = field.current?.getBoundingClientRect();
    if (bounds) setCamera(fitCamera(currentNodes.current, bounds.width, bounds.height));
  }
  useEffect(() => {
    const element = field.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      const bounds = element.getBoundingClientRect();
      setCamera(fitCamera(currentNodes.current, bounds.width, bounds.height));
    });
    observer.observe(element);
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const bounds = element.getBoundingClientRect();
      setCamera((previous) => zoomAt(previous, { x: event.clientX - bounds.left, y: event.clientY - bounds.top }, previous.zoom * Math.exp(-event.deltaY * .0015)));
    };
    element.addEventListener("wheel", wheel, { passive: false });
    return () => { observer.disconnect(); element.removeEventListener("wheel", wheel); };
  }, []);
  useEffect(() => { fit(); }, [signature]);
  useEffect(() => {
    const node = currentNodes.current.find((item) => item.id === focusRequest?.id);
    const bounds = field.current?.getBoundingClientRect();
    if (node && bounds) setCamera((previous) => ({ zoom: previous.zoom, x: bounds.width / 2 - node.x * previous.zoom, y: bounds.height / 2 - node.y * previous.zoom }));
  }, [focusRequest]);

  function start(event: PointerEvent<HTMLElement>, node?: MapNode) {
    if (event.button !== 0) return;
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    gesture.current = { type: node ? "node" : "pan", pointer: event.pointerId, start: { x: event.clientX, y: event.clientY }, origin: node ? offsets[node.id] ?? { x: 0, y: 0 } : { x: camera.x, y: camera.y }, nodeId: node?.id, zoom: camera.zoom };
    suppressedClick.current = false;
  }
  function move(event: PointerEvent<HTMLElement>) {
    const current = gesture.current;
    if (!current || current.pointer !== event.pointerId) return;
    const dx = event.clientX - current.start.x;
    const dy = event.clientY - current.start.y;
    if (Math.hypot(dx, dy) < 4 && !suppressedClick.current) return;
    suppressedClick.current = true; setDragging(true);
    if (current.type === "pan") setCamera((previous) => ({ ...previous, x: current.origin.x + dx, y: current.origin.y + dy }));
    else if (current.nodeId) setOffsets((previous) => ({ ...previous, [current.nodeId!]: { x: current.origin.x + dx / current.zoom, y: current.origin.y + dy / current.zoom } }));
  }
  function end(event: PointerEvent<HTMLElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    gesture.current = null; setDragging(false);
  }
  function changeZoom(factor: number) {
    const bounds = field.current?.getBoundingClientRect();
    if (bounds) setCamera((previous) => zoomAt(previous, { x: bounds.width / 2, y: bounds.height / 2 }, previous.zoom * factor));
  }
  const positions = new Map(currentNodes.current.map((node) => [node.id, node]));

  return <div className={`mission-map${dragging ? " is-dragging" : ""}`} ref={field} role="region" aria-label="Interactive mission map" tabIndex={0}
    onPointerDown={(event) => start(event)} onPointerMove={move} onPointerUp={end} onPointerCancel={end}
    onKeyDown={(event) => { if (event.target !== event.currentTarget) return;
      if (event.key === "+" || event.key === "=") { event.preventDefault(); changeZoom(1.2); }
      if (event.key === "-") { event.preventDefault(); changeZoom(1 / 1.2); }
      if (event.key === "0") { event.preventDefault(); fit(); }
    }}>
    <div className="map-coordinate map-coordinate--top mono" aria-hidden="true">KAGE / FIELD SYSTEM<br />{String(model.nodes.length).padStart(2, "0")} ENTITIES IN VIEW</div>
    <div className="map-world" style={{ transform: `translate(${camera.x}px,${camera.y}px) scale(${camera.zoom})` }}>
      {model.nodes.some((node) => node.kind === "agent") && <><div className="map-orbit map-orbit--outer" /><div className="map-orbit map-orbit--inner" /></>}
      <svg className="map-connections" width={Math.max(1800, ...currentNodes.current.map((node) => node.x + node.width))} height={Math.max(1100, ...currentNodes.current.map((node) => node.y + node.height))} aria-hidden="true">
        {model.edges.map((edge) => {
          const from = positions.get(edge.from); const to = positions.get(edge.to);
          if (!from || !to) return null;
          const bend = (from.x + to.x) / 2;
          const highlighted = edge.from === selectedId || edge.to === selectedId;
          return <path key={edge.id} className={`map-edge map-edge--${edge.kind}${edge.active ? " is-active" : ""}${highlighted ? " is-selected" : ""}`} d={`M ${from.x} ${from.y} C ${bend} ${from.y}, ${bend} ${to.y}, ${to.x} ${to.y}`} />;
        })}
      </svg>
      {currentNodes.current.map((node) => <button key={node.id} className={`field-node field-node--${node.kind}${node.id === selectedId ? " is-selected" : ""}`} data-node-id={node.id} data-node-x={node.x} data-node-y={node.y}
        style={{ left: node.x - node.width / 2, top: node.y - node.height / 2, width: node.width, minHeight: node.height }}
        aria-pressed={node.id === selectedId} title={node.title} aria-label={`${node.title}, ${node.subtitle}, ${node.state}`}
        onPointerDown={(event) => start(event, node)} onPointerMove={move} onPointerUp={end} onPointerCancel={end}
        onClick={() => { if (suppressedClick.current) { suppressedClick.current = false; return; } onSelect(node); }}
        onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) return;
          event.preventDefault(); event.stopPropagation();
          const x = event.key === "ArrowLeft" ? -20 : event.key === "ArrowRight" ? 20 : 0;
          const y = event.key === "ArrowUp" ? -20 : event.key === "ArrowDown" ? 20 : 0;
          setOffsets((previous) => ({ ...previous, [node.id]: { x: (previous[node.id]?.x ?? 0) + x, y: (previous[node.id]?.y ?? 0) + y } }));
        }}>
        {node.kind === "mission" ? <><span className="nucleus-halo" aria-hidden="true" /><span className="nucleus-kanji" aria-hidden="true">影</span><strong className="nucleus-title">MISSION CORE</strong><span className="field-node__state mono" data-state={node.state}>{node.state.replaceAll("_", " ")}</span></>
          : <><span className="field-node__index mono">{node.kind === "agent" ? "GUILD ROLE" : node.kind.toUpperCase()}</span>
            <div className="field-node__identity"><span className="field-node__glyph" aria-hidden="true">{node.glyph}</span><div><strong>{node.title}</strong><span>{node.subtitle}</span></div></div>
            <span className="field-node__state mono" data-state={node.state}><i aria-hidden="true" />{node.state.replaceAll("_", " ")}</span><span className="node-drag-mark" aria-hidden="true">⠿</span></>}
      </button>)}
    </div>
    <div className="map-tools" onPointerDown={(event) => event.stopPropagation()}>
      <button aria-label="Zoom out" onClick={() => changeZoom(1 / 1.2)}><Minus size={16} /></button>
      <span className="mono" aria-label="Map zoom">{Math.round(camera.zoom * 100)}%</span>
      <button aria-label="Zoom in" onClick={() => changeZoom(1.2)}><Plus size={16} /></button>
      <button aria-label="Fit mission map" onClick={fit}><Crosshair size={16} /></button>
      <button aria-label="Reset node layout" onClick={() => { setOffsets({}); const bounds = field.current?.getBoundingClientRect(); if (bounds) setCamera(fitCamera(model.nodes, bounds.width, bounds.height)); }}><Maximize2 size={16} /></button>
    </div>
    <p className="map-gesture"><Move size={13} aria-hidden="true" /> Drag to explore · scroll to zoom · select a node</p>
  </div>;
}
