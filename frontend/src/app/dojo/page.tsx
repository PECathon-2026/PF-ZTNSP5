import type { Metadata } from "next";
import { Suspense } from "react";
import { MissionDojo } from "@/components/mission-dojo";

export const metadata: Metadata = { title: "Dojo" };

export default function DojoPage() {
  return <Suspense fallback={<div className="interior-page dojo-page">Loading mission…</div>}><MissionDojo /></Suspense>;
}
