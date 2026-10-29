"use client";

import { ProofDesk } from "./proof-desk";

export function EvidenceScreen({ missionId }: { missionId: string }) {
  return <ProofDesk key={missionId} missionId={missionId} />;
}
