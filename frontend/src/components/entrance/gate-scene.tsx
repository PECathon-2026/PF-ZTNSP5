"use client";

import { Component, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Sparkles } from "@react-three/drei";
import { Vector3 } from "three";
import { Pause, Play, MoveUpRight } from "lucide-react";
import { Lantern, NightBackdrop, Torii } from "./scene-architecture";

class SceneBoundary extends Component<{ children: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() { return this.state.failed ? null : this.props.children; }
}

function CameraRig({ motion, crossing, inside, pointer }: { motion: boolean; crossing: boolean; inside: boolean; pointer: { current: { x: number; y: number } } }) {
  const position = useRef(new Vector3());
  const look = useRef(new Vector3(.2, 1.8, -6));
  const destination = useRef(new Vector3());
  useFrame(({ camera }, delta) => {
    position.current.set(crossing ? 3 : inside ? 3 : -.6 + pointer.current.x * .75, crossing ? 2.2 : 2.4 - pointer.current.y * .22, crossing ? -2 : inside ? 3.8 : 11.5);
    destination.current.set(crossing || inside ? 3 : .2, 1.8, -8);
    const damping = motion ? 1 - Math.exp(-Math.min(delta, .1) * (crossing ? 5 : 2.5)) : 1;
    camera.position.lerp(position.current, damping);
    look.current.lerp(destination.current, damping);
    camera.lookAt(look.current);
  });
  return null;
}

function Avenue({ motion }: { motion: boolean }) {
  return <>
    <color attach="background" args={["#0b1018"]} /><fogExp2 attach="fog" args={["#11151b", .025]} />
    <ambientLight intensity={.65} color="#b8c4d3" /><directionalLight position={[8, 11, 5]} intensity={2.5} color="#d9c79e" />
    <pointLight position={[1, 3, 4]} intensity={18} color="#bb3434" distance={13} />
    <NightBackdrop />
    {[0, -5, -10, -15, -20].map((z) => <Torii key={z} z={z} />)}
    {[3, -3, -8, -13].flatMap((z) => [<Lantern key={`l${z}`} x={.2} z={z} />, <Lantern key={`r${z}`} x={5.8} z={z} />])}
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -.91, 0]}><planeGeometry args={[100, 100]} /><meshStandardMaterial color="#12151b" roughness={.36} metalness={.32} /></mesh>
    {Array.from({ length: 17 }, (_, index) => <mesh key={index} position={[3, -.88, 8 - index * 1.7]}><boxGeometry args={[2.3, .045, 1.3]} /><meshStandardMaterial color="#2b2c2c" roughness={.75} /></mesh>)}
    <Sparkles count={70} scale={[18, 8, 17]} position={[2, 3, -4]} speed={motion ? .17 : 0} size={2} color="#d0ad68" opacity={.5} />
  </>;
}

export default function GateScene({ crossing = false, inside = false, onInside }: { crossing?: boolean; inside?: boolean; onInside?: () => void }) {
  const [motion, setMotion] = useState(false);
  const [visible, setVisible] = useState(true);
  const [failed, setFailed] = useState(false);
  const pointer = useRef({ x: 0, y: 0 });
  const wrapper = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setMotion(!media.matches);
    update(); media.addEventListener("change", update);
    const visibility = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", visibility);
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting && !document.hidden));
    if (wrapper.current) observer.observe(wrapper.current);
    const move = (event: globalThis.PointerEvent) => {
      const bounds = wrapper.current?.getBoundingClientRect();
      if (bounds) pointer.current = { x: Math.max(-1, Math.min(1, (event.clientX - bounds.left) / bounds.width * 2 - 1)), y: Math.max(-1, Math.min(1, (event.clientY - bounds.top) / bounds.height * 2 - 1)) };
    };
    window.addEventListener("pointermove", move, { passive: true });
    return () => { media.removeEventListener("change", update); document.removeEventListener("visibilitychange", visibility); window.removeEventListener("pointermove", move); observer.disconnect(); };
  }, []);
  return <div className="threshold-scene" ref={wrapper} data-view={inside ? "inside" : "entrance"}>
    <div className="threshold-canvas" aria-hidden="true">
      {!failed && <SceneBoundary onFailure={() => setFailed(true)}><Canvas camera={{ position: [-.6, 2.4, 11.5], fov: 49 }} dpr={[1, 1.5]} frameloop={motion && visible ? "always" : "demand"}
        gl={{ antialias: true, alpha: true, powerPreference: "low-power" }} fallback={null}
        onCreated={({ camera, gl }) => { camera.lookAt(.2, 1.8, -6); gl.domElement.addEventListener("webglcontextlost", () => setFailed(true), { once: true }); }}>
        <Suspense fallback={null}><Avenue motion={motion && visible} /></Suspense>
        <CameraRig motion={motion && visible} crossing={crossing} inside={inside} pointer={pointer} />
      </Canvas></SceneBoundary>}
    </div>
    <div className="threshold-scene-controls">
      {failed ? <span className="mono">STATIC ENVIRONMENT</span> : <>
        <button onClick={() => setMotion((value) => !value)} aria-label={motion ? "Pause scene motion" : "Enable scene motion"}>{motion ? <Pause size={13} /> : <Play size={13} />}<span>{motion ? "Pause motion" : "Enable motion"}</span></button>
        <button onClick={onInside} aria-pressed={inside}><MoveUpRight size={14} /><span>{inside ? "Return to entrance" : "View from inside"}</span></button>
      </>}
    </div>
  </div>;
}
