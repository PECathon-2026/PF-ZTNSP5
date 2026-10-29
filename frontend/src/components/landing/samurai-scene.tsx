"use client";

import { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { BufferAttribute, BufferGeometry, Group, MathUtils, Points } from "three";
import type { RefObject } from "react";
import type { MotionValues } from "./types";

const clanColors = ["#c99a3a", "#b92a28", "#9aa9a0", "#b5ac9a"];

function ArmorPiece({ position, rotation = [0, 0, 0], size, color = "#16191b" }: {
  position: [number, number, number]; rotation?: [number, number, number];
  size: [number, number, number]; color?: string;
}) {
  return <mesh position={position} rotation={rotation} castShadow><boxGeometry args={size} /><meshStandardMaterial color={color} metalness={0.5} roughness={0.57} /></mesh>;
}

function EmberField() {
  const ref = useRef<Points>(null);
  const geometry = useMemo(() => {
    // Fixed positions avoid a visibly different particle field on each navigation.
    const coords = new Float32Array(75 * 3);
    for (let i = 0; i < 75; i++) {
      const seed = Math.sin(i * 127.1 + 47.3) * 43758.5453;
      const fraction = seed - Math.floor(seed);
      coords[i * 3] = (fraction - 0.5) * 10;
      coords[i * 3 + 1] = ((i * 17) % 73) / 73 * 8 - 4;
      coords[i * 3 + 2] = -1.5 + ((i * 37) % 61) / 61 * 3;
    }
    const result = new BufferGeometry();
    result.setAttribute("position", new BufferAttribute(coords, 3));
    return result;
  }, []);
  useFrame((_, delta) => { if (ref.current) ref.current.rotation.y += Math.min(delta, 0.05) * 0.012; });
  return <points ref={ref} geometry={geometry}><pointsMaterial color="#e8ad63" size={0.035} sizeAttenuation transparent opacity={0.65} depthWrite={false} /></points>;
}

function Samurai({ motion, agentIndex }: { motion: RefObject<MotionValues>; agentIndex: number }) {
  const rig = useRef<Group>(null);
  const sword = useRef<Group>(null);
  const accent = clanColors[agentIndex] ?? clanColors[0];

  useFrame((_, delta) => {
    if (!rig.current) return;
    const damping = Math.min(delta, 0.05);
    const { mouseX, mouseY, scroll } = motion.current;
    rig.current.rotation.y = MathUtils.damp(rig.current.rotation.y, -0.25 + mouseX * 0.33 + scroll * 0.52, 3, damping);
    rig.current.rotation.x = MathUtils.damp(rig.current.rotation.x, -mouseY * 0.08, 3, damping);
    rig.current.position.y = MathUtils.damp(rig.current.position.y, Math.sin(scroll * Math.PI) * 0.16, 2.5, damping);
    if (sword.current) sword.current.rotation.z = MathUtils.damp(sword.current.rotation.z, -0.47 + scroll * 0.32, 2.4, damping);
  });

  return <group ref={rig} position={[1.7, -0.27, 0]} scale={0.85}>
    {/* A low-poly original figure: helmet, layered armor, hakama and one illuminated blade. */}
    <mesh position={[0, 2.15, 0]} castShadow><sphereGeometry args={[0.33, 8, 6]} /><meshStandardMaterial color="#19191a" metalness={0.48} roughness={0.5} /></mesh>
    <mesh position={[0, 2.28, 0]} rotation={[0, 0, 0]} castShadow><sphereGeometry args={[0.5, 9, 5, 0, Math.PI * 2, 0, Math.PI / 2]} /><meshStandardMaterial color="#252021" metalness={0.55} roughness={0.42} /></mesh>
    <ArmorPiece position={[0, 2.35, 0.32]} size={[0.75, 0.08, 0.3]} color={accent} />
    <mesh position={[0, 2.67, 0]} rotation={[0, 0, Math.PI]} castShadow><coneGeometry args={[0.23, 0.4, 4]} /><meshStandardMaterial color={accent} metalness={0.68} roughness={0.38} /></mesh>
    <ArmorPiece position={[0, 2.0, 0.27]} size={[0.57, 0.22, 0.17]} color="#080a0a" />
    <ArmorPiece position={[0, 1.28, 0]} size={[0.86, 1.06, 0.46]} color="#191b1d" />
    <ArmorPiece position={[0, 1.53, 0.28]} size={[0.63, 0.17, 0.1]} color={accent} />
    <ArmorPiece position={[0, 1.25, 0.28]} size={[0.7, 0.12, 0.1]} color={accent} />
    <ArmorPiece position={[0, 0.95, 0.28]} size={[0.72, 0.11, 0.1]} color={accent} />
    <ArmorPiece position={[0, 0.74, 0.03]} size={[0.92, 0.18, 0.55]} color="#3a2822" />
    <ArmorPiece position={[-0.64, 1.64, 0]} rotation={[0, 0, -0.32]} size={[0.54, 0.37, 0.57]} color="#2d2524" />
    <ArmorPiece position={[0.64, 1.64, 0]} rotation={[0, 0, 0.32]} size={[0.54, 0.37, 0.57]} color="#2d2524" />
    <ArmorPiece position={[-0.83, 1.04, 0]} rotation={[0, 0, -0.12]} size={[0.3, 0.9, 0.35]} />
    <ArmorPiece position={[0.83, 1.04, 0]} rotation={[0, 0, 0.12]} size={[0.3, 0.9, 0.35]} />
    <ArmorPiece position={[-0.28, 0.02, 0]} rotation={[0, 0, 0.08]} size={[0.46, 1.25, 0.48]} color="#191b1d" />
    <ArmorPiece position={[0.28, 0.02, 0]} rotation={[0, 0, -0.08]} size={[0.46, 1.25, 0.48]} color="#191b1d" />
    <ArmorPiece position={[-0.33, -0.65, 0.15]} size={[0.48, 0.14, 0.65]} color="#101111" />
    <ArmorPiece position={[0.33, -0.65, 0.15]} size={[0.48, 0.14, 0.65]} color="#101111" />
    <group ref={sword} position={[0.95, 1.05, 0.25]} rotation={[0, 0, -0.47]}>
      <mesh position={[0, 0.05, 0]}><cylinderGeometry args={[0.07, 0.07, 0.65, 6]} /><meshStandardMaterial color="#422d26" /></mesh>
      <mesh position={[0, 0.43, 0]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.17, 0.035, 4, 8]} /><meshStandardMaterial color={accent} metalness={0.65} /></mesh>
      <mesh position={[0, 1.28, 0]}><cylinderGeometry args={[0.012, 0.065, 1.64, 3]} /><meshStandardMaterial color="#f6e4be" emissive={accent} emissiveIntensity={1.25} metalness={0.8} roughness={0.24} /></mesh>
      <pointLight position={[0, 1.3, 0.2]} color={accent} intensity={1.3} distance={3.5} />
    </group>
    <mesh position={[0, -0.9, 0]} rotation={[-Math.PI / 2, 0, 0]}><circleGeometry args={[1.2, 24]} /><meshBasicMaterial color="#0b0909" transparent opacity={0.36} depthWrite={false} /></mesh>
  </group>;
}

export default function SamuraiScene({ motion, agentIndex, onReady }: {
  motion: RefObject<MotionValues>; agentIndex: number; onReady: () => void;
}) {
  return <Canvas
    aria-hidden="true"
    camera={{ position: [0, 0.7, 8.2], fov: 42 }}
    dpr={[1, 1.5]}
    gl={{ alpha: true, antialias: true, powerPreference: "high-performance" }}
    onCreated={onReady}
  >
    <ambientLight intensity={1.6} color="#cfbda6" />
    <directionalLight position={[4, 6, 6]} intensity={3.2} color="#ffe3b2" />
    <directionalLight position={[-4, 3, -2]} intensity={2.5} color="#b0271b" />
    <Samurai motion={motion} agentIndex={agentIndex} />
    <EmberField />
  </Canvas>;
}
