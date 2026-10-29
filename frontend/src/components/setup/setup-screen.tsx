"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { RepositoryPanel, restoreActiveRepository } from "./repository-panel";
import { MissionBrief } from "./mission-brief";
import type { StoredRepository } from "@/lib/types";

export function SetupScreen() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [connected, setConnected] = useState<StoredRepository | null>(null);
  const [focusRequest, setFocusRequest] = useState(0);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    const stored = restoreActiveRepository();
    if (stored) setConnected(stored);
    setRestored(true);
  }, []);

  useEffect(() => {
    if (searchParams.get("focus") === "repository") setFocusRequest((value) => value + 1);
  }, [searchParams]);

  return (
    <div className="content-width setup-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">NEW MISSION · THE BRIEF</p>
          <h1>Commission the work</h1>
          <p className="lede">
            Select the repository, describe the change, and define what counts as done. Nothing is
            executed until the guild is given a mission — and nothing is applied without your
            approval later.
          </p>
        </div>
      </header>

      <div className="setup-grid">
        <RepositoryPanel
          connected={connected}
          onConnected={setConnected}
          focusRequest={focusRequest}
        />
        {restored ? (
          <MissionBrief connected={connected} onStarted={(missionId) => router.push(`/missions/${missionId}`)} />
        ) : (
          <section className="panel setup-panel" aria-busy="true">
            <div className="panel-head">
              <span className="panel-title">02 · INTENT</span>
            </div>
            <div className="setup-panel__body">
              <div className="state-block">
                <span className="spinner" aria-hidden="true" />
                <p>Restoring your last repository session…</p>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
