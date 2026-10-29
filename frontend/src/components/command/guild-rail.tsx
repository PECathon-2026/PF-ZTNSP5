"use client";

import { GUILD } from "@/lib/status";
import type { MissionStatus, MissionTask } from "@/lib/types";

type GuildRailProps = {
  tasks: MissionTask[];
  status: MissionStatus;
};

export function GuildRail({ tasks, status }: GuildRailProps) {
  const activeLike = ["RUNNING", "CHECKING", "REPAIRING", "REVIEWING", "VERIFYING", "APPLYING"].includes(status);

  return (
    <section className="panel guild-rail" aria-labelledby="guild-rail-title">
      <div className="panel-head">
        <span className="panel-title" id="guild-rail-title">
          THE GUILD
        </span>
      </div>
      <ul className="guild-rail__list">
        {GUILD.map((member) => {
          const owned = tasks.filter((task) => task.owner_agent === member.id);
          const done = owned.filter((task) => task.status === "DONE").length;
          return (
            <li key={member.id} className="guild-rail__member">
              <span className="guild-rail__glyph" aria-hidden="true">
                {member.glyph}
              </span>
              <div className="guild-rail__body">
                <p className="guild-rail__name">
                  {member.name}
                  <span className="guild-rail__role">{member.role}</span>
                </p>
                <p className="guild-rail__count mono">
                  {owned.length === 0 ? "no tasks assigned" : `${done}/${owned.length} tasks done`}
                </p>
                <p className="guild-rail__purpose">{member.purpose}</p>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="guild-rail__note">
        {activeLike
          ? "Roles below reflect planned ownership recorded with each task."
          : "No agent is executing right now. These roles describe who will act when the mission runs — the counts come from the task plan the Shogun recorded."}
      </p>
    </section>
  );
}
