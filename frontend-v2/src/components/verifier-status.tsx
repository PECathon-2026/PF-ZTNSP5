"use client";

import { verifierStatus } from "@/lib/mission";
import type { Detail, MissionEvent } from "@/lib/types";

export function VerifierStatus({ detail, events }: { detail: Detail; events: MissionEvent[] }) {
  const status = verifierStatus(detail, events);
  return <section className="historical-strip" role="status" aria-live="polite">
    <strong>Independent verifier: {status}</strong>
    <span> · Checks recorded test evidence and review completion after Shadow Council’s source review.</span>
  </section>;
}
