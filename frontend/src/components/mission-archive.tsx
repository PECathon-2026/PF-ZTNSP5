"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Mission } from "@/lib/backend";

export function MissionArchive() {
  const [missions, setMissions] = useState<Mission[] | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api<Mission[]>("/api/missions?limit=10", { signal: controller.signal })
      .then((items) => setMissions(items)).catch(() => { if (!controller.signal.aborted) setMissions([]); });
    return () => controller.abort();
  }, []);
  return <div className="archive-empty"><span aria-hidden="true">影</span><div>
    <h3>{missions?.length ? "Recent missions" : missions ? "No mission history yet" : "Loading mission history…"}</h3>
    {missions?.map((mission) => <p key={mission.id}><Link href={`/dojo?mission=${encodeURIComponent(mission.id)}`}>{mission.request_text.slice(0, 90)} · {mission.status} ↗</Link></p>)}
    {!missions?.length && <p>Saved missions and outcomes appear here when the backend is available.</p>}
    <Link href="/setup" className="text-action">Prepare a mission ↗</Link>
  </div></div>;
}
