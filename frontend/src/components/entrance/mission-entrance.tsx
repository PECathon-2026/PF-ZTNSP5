"use client";

import { EntranceHero } from "./entrance-hero";
import { RecentMissions } from "./recent-missions";
import { GuildRoster, MissionLifecycle } from "./guild-roster";
import { ReadinessProbe } from "@/components/shell/connection-status";
import { useMissions } from "@/lib/use-missions";

export function MissionEntrance() {
  const { missions, loading, error, reload } = useMissions();
  const lastMission = missions.length > 0 ? missions[0] : null;

  return (
    <div className="entrance">
      <EntranceHero lastMission={lastMission} />

      <div className="content-width entrance-body">
        <RecentMissions missions={missions} loading={loading} error={error} onRetry={reload} />
        <hr className="kintsugi-line entrance-rule" />
        <GuildRoster />
        <hr className="kintsugi-line entrance-rule" />
        <MissionLifecycle />
        <hr className="kintsugi-line entrance-rule" />

        <section className="entrance-block" aria-labelledby="readiness-title">
          <header className="block-head">
            <div>
              <p className="block-index">04 / READINESS</p>
              <h2 id="readiness-title">Before the mission</h2>
            </div>
            <p className="block-aside">
              Only confirmed capability earns a ready state. Unknown stays unknown.
            </p>
          </header>
          <ReadinessProbe />
        </section>
      </div>
    </div>
  );
}
