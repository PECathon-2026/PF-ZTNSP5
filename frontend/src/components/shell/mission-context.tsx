"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { MissionStatus } from "@/lib/types";
import { stageOf, type StageKey } from "@/lib/status";

export type MissionBrief = {
  id: string;
  request: string;
  repositoryId: string;
  status: MissionStatus;
  stage: StageKey;
  activeCandidateId: string | null;
};

type MissionSessionValue = {
  brief: MissionBrief | null;
  setBrief: (brief: MissionBrief | null) => void;
};

const MissionSessionContext = createContext<MissionSessionValue | null>(null);

export function MissionSessionProvider({ children }: { children: ReactNode }) {
  const [brief, setBriefState] = useState<MissionBrief | null>(null);

  const setBrief = useCallback((next: MissionBrief | null) => {
    setBriefState((previous) => {
      if (!next && !previous) return previous;
      if (next && previous && JSON.stringify(next) === JSON.stringify(previous)) return previous;
      return next;
    });
  }, []);

  const value = useMemo(() => ({ brief, setBrief }), [brief, setBrief]);
  return <MissionSessionContext.Provider value={value}>{children}</MissionSessionContext.Provider>;
}

export function useMissionSession(): MissionSessionValue {
  const context = useContext(MissionSessionContext);
  if (!context) throw new Error("useMissionSession must be used inside MissionSessionProvider");
  return context;
}

export function useMissionBriefSync(brief: MissionBrief | null): void {
  const { setBrief } = useMissionSession();
  useEffect(() => {
    setBrief(brief);
    return () => setBrief(null);
  }, [brief, setBrief]);
}

export function briefFromMission(mission: {
  id: string;
  request_text: string;
  repository_id: string;
  status: MissionStatus;
  active_candidate_id: string | null;
}): MissionBrief {
  return {
    id: mission.id,
    request: mission.request_text,
    repositoryId: mission.repository_id,
    status: mission.status,
    stage: stageOf(mission.status),
    activeCandidateId: mission.active_candidate_id,
  };
}
