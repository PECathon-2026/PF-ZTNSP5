"use client";

import { MissionCockpit } from "@/components/cockpit/cockpit-screen";

export function CommandScreen({ missionId }: { missionId: string }) {
  return <MissionCockpit key={missionId} missionId={missionId} />;
}
