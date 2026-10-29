import type { Metadata } from "next";
import { Suspense } from "react";
import { SetupScreen } from "@/components/setup/setup-screen";
import "../tree.css";
import "./setup.css";

export const metadata: Metadata = { title: "Commission a mission" };

export default function SetupPage() {
  return (
    <Suspense
      fallback={
        <div className="content-width setup-page">
          <div className="state-block">
            <span className="spinner" aria-hidden="true" />
            <p>Preparing the mission desk…</p>
          </div>
        </div>
      }
    >
      <SetupScreen />
    </Suspense>
  );
}
