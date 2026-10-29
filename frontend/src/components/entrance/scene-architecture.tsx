"use client";

import { useTexture } from "@react-three/drei";

export function Torii({ z, scale = 1 }: { z: number; scale?: number }) {
  return <group position={[3, -.9, z]} scale={scale}>
    {[-1.75, 1.75].map((x) => <group key={x} position={[x, 0, 0]}>
      <mesh position={[0, 2.5, 0]}><cylinderGeometry args={[.14, .24, 5, 16]} /><meshStandardMaterial color="#861a22" roughness={.55} metalness={.12} /></mesh>
      <mesh position={[0, .25, 0]}><boxGeometry args={[.55, .5, .55]} /><meshStandardMaterial color="#171a20" roughness={.9} /></mesh>
      <mesh position={[0, 3.9, 0]}><boxGeometry args={[.31, .12, .68]} /><meshStandardMaterial color="#b08842" metalness={.45} roughness={.5} /></mesh>
    </group>)}
    <mesh position={[0, 5.1, 0]}><boxGeometry args={[5.25, .27, .62]} /><meshStandardMaterial color="#241b20" roughness={.6} /></mesh>
    {[-1, 1].map((side) => <mesh key={side} position={[side * 2.48, 5.19, 0]} rotation={[0, 0, side * .15]}><boxGeometry args={[.92, .25, .62]} /><meshStandardMaterial color="#241b20" /></mesh>)}
    <mesh position={[0, 4.83, 0]}><boxGeometry args={[5, .21, .4]} /><meshStandardMaterial color="#9c222b" roughness={.6} /></mesh>
    <mesh position={[0, 3.9, 0]}><boxGeometry args={[4.4, .22, .3]} /><meshStandardMaterial color="#93232b" roughness={.5} /></mesh>
    <mesh position={[0, 4.37, 0]}><boxGeometry args={[.16, .7, .23]} /><meshStandardMaterial color="#9c7640" metalness={.5} roughness={.45} /></mesh>
  </group>;
}

export function Lantern({ x, z }: { x: number; z: number }) {
  return <group position={[x, .5, z]}>
    <mesh><boxGeometry args={[.46, .66, .46]} /><meshStandardMaterial color="#dbbc77" emissive="#b88a3b" emissiveIntensity={1.3} /></mesh>
    {[-.24, .24].map((edge) => <group key={edge} position={[edge, 0, 0]}>
      <mesh position={[0, 0, .24]}><boxGeometry args={[.05, .76, .05]} /><meshStandardMaterial color="#302316" /></mesh>
      <mesh position={[0, 0, -.24]}><boxGeometry args={[.05, .76, .05]} /><meshStandardMaterial color="#302316" /></mesh>
    </group>)}
    <mesh position={[0, .42, 0]} rotation={[0, Math.PI / 4, 0]}><coneGeometry args={[.5, .21, 4]} /><meshStandardMaterial color="#232127" /></mesh>
    <mesh position={[0, -.41, 0]}><boxGeometry args={[.58, .09, .58]} /><meshStandardMaterial color="#232127" /></mesh>
    <mesh position={[0, -.9, 0]}><cylinderGeometry args={[.055, .1, 1, 8]} /><meshStandardMaterial color="#1a1b20" /></mesh>
    <pointLight color="#dbac5e" intensity={4} distance={5} decay={2} />
  </group>;
}

export function NightBackdrop() {
  const image = useTexture("/images/entrance-night.jpg");
  return <mesh position={[-3, 6, -29]}><planeGeometry args={[90, 50]} /><meshBasicMaterial map={image} transparent opacity={.33} toneMapped={false} fog={false} depthWrite={false} /></mesh>;
}
