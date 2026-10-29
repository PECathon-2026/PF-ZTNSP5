"use client";

import { useEffect, useRef } from "react";
import { eventLabel, eventTone, formatClock, formatInstant } from "@/lib/status";
import type { MissionEventsState } from "@/lib/use-missions";

type TimelineProps = {
  events: MissionEventsState;
};

function payloadLines(payload: Record<string, unknown>): string[] {
  return Object.entries(payload)
    .slice(0, 5)
    .map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : String(value)}`);
}

export function Timeline({ events }: TimelineProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true);

  useEffect(() => {
    if (stickToBottom.current) endRef.current?.scrollIntoView({ block: "nearest" });
  }, [events.events.length]);

  return (
    <section className="panel timeline" aria-labelledby="timeline-title">
      <div className="panel-head">
        <span className="panel-title" id="timeline-title">
          TIMELINE
        </span>
        <span
          className={events.phase === "error" ? "status" : "status"}
          data-tone={events.phase === "live" ? "jade" : events.phase === "error" ? "warn" : "info"}
          role="status"
        >
          {events.phase === "live" ? "◉ LIVE · POLLING 3S" : events.phase === "error" ? "⚠ RECONNECTING" : "… CONNECTING"}
        </span>
      </div>

      {events.phase === "error" && events.error && (
        <p className="timeline__error field-error" role="alert">
          {events.error}
        </p>
      )}

      <div
        className="timeline__scroll"
        onScroll={(event) => {
          const el = event.currentTarget;
          stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
        }}
      >
        {events.events.length === 0 ? (
          <div className="state-block state-block--inline">
            <span className="state-mark" aria-hidden="true">
              記
            </span>
            <h3>No events recorded yet</h3>
            <p>
              Every action the guild takes is written here in order — task assignments, tool runs,
              candidates, findings. Nothing has been recorded for this mission so far.
            </p>
          </div>
        ) : (
          <ol className="timeline__list">
            {events.events.map((event) => (
              <li key={event.sequence} data-tone={eventTone(event.event_type)}>
                <span className="timeline__seq mono">#{String(event.sequence).padStart(3, "0")}</span>
                <div className="timeline__body">
                  <p className="timeline__label">
                    {eventLabel(event.event_type)}
                    <span className="timeline__source mono">{event.source}</span>
                  </p>
                  {payloadLines(event.display_payload ?? {}).length > 0 && (
                    <ul className="timeline__payload mono">
                      {payloadLines(event.display_payload ?? {}).map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  )}
                  <p className="timeline__refs mono">
                    {event.task_id && <span>task {event.task_id.slice(0, 10)}</span>}
                    {event.candidate_id && <span>candidate {event.candidate_id.slice(0, 10)}</span>}
                    {event.evidence_ids.length > 0 && <span>{event.evidence_ids.length} evidence</span>}
                    <span title={formatInstant(event.created_at)}>{formatClock(event.created_at)}</span>
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
        <div ref={endRef} />
      </div>
    </section>
  );
}
