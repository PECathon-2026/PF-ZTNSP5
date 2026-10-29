import type { Metadata } from "next";
import { Suspense } from "react";
import { MissionsScreen } from "@/components/missions/missions-screen";
import "./missions.css";

export const metadata: Metadata = { title: "Missions" };

export default function MissionsPage() {
  return (
    <Suspense fallback={
      <div className="content-width missions-page">
        <div className="state-block">
          <span className="spinner" aria-hidden="true" />
          <p>Loading missions…</p>
        </div>
      </div>
    }>
      <MissionsScreen />
    </Suspense>
  );
}
