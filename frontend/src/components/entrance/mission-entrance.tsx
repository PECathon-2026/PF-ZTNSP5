"use client";

import { useState } from "react";
import { EntranceHero } from "./entrance-hero";
import { RecentMissions } from "./recent-missions";
import { GuildRoster } from "./guild-roster";
import { ReadinessProbe } from "@/components/shell/connection-status";
import { Modal } from "@/components/mission/modal";
import { useMissions } from "@/lib/use-missions";

export function MissionEntrance() {
  const { missions, loading, error, reload } = useMissions();
  const [drawer, setDrawer] = useState<"archive" | "guild" | "readiness" | null>(null);
  return <div className="immersive-entrance">
    <EntranceHero lastMission={missions[0] ?? null} missionCount={missions.length} loading={loading} archiveError={error}
      onArchive={() => setDrawer("archive")} onGuild={() => setDrawer("guild")} onReadiness={() => setDrawer("readiness")} />
    {drawer && <Modal title={drawer === "archive" ? "Mission archive" : drawer === "guild" ? "Meet the guild" : "Runtime readiness"} onClose={() => setDrawer(null)}>
      <div className="threshold-info">
        {drawer === "archive" ? <RecentMissions missions={missions} loading={loading} error={error} onRetry={reload} />
          : drawer === "guild" ? <GuildRoster /> : <><p className="threshold-readiness-intro">Capabilities reported by your connected backend. A responding API does not imply that model reasoning or container execution is ready.</p><ReadinessProbe /></>}
      </div>
    </Modal>}
  </div>;
}
