"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { endpoint, getMission, history } from "./api";
import { mergeEvents } from "./mission";
import type { Detail, MissionEvent } from "./types";

export function useMission(id: string) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [repository, setRepository] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("connecting");
  const generation = useRef(0);
  const refreshSequence = useRef(0);
  const refresh = useCallback(async () => {
    const current = generation.current;
    const sequence = ++refreshSequence.current;
    const next = await getMission(id);
    if (current === generation.current && sequence === refreshSequence.current) { setDetail(next); setError(""); }
    return next;
  }, [id]);

  useEffect(() => {
    generation.current++;
    let disposed = false;
    let source: EventSource | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const abort = new AbortController();
    let cursor = 0;
    setDetail(null); setEvents([]); setError(""); setConnection("connecting");
    const reconcile = () => {
      clearTimeout(timer);
      timer = setTimeout(() => { if (!disposed) refresh().catch(e => { if (!disposed) setError(e.message); }); }, 180);
    };
    async function start() {
      try {
        const [snapshot, recorded] = await Promise.all([getMission(id, abort.signal), history(id, abort.signal)]);
        if (disposed) return;
        setDetail(snapshot); setRepository(recorded.repository); setEvents(recorded.events);
        if (["APPLIED", "REJECTED", "CANCELLED"].includes(snapshot.mission.status)) {
          setConnection("recorded");
          return;
        }
        cursor = recorded.events.at(-1)?.sequence || 0;
        source = new EventSource(endpoint(`/missions/${encodeURIComponent(id)}/events?after=${cursor}`));
        source.onopen = () => { if (!disposed) { setConnection("live"); reconcile(); } };
        source.onerror = () => { if (!disposed) setConnection("reconnecting"); };
        source.addEventListener("mission", event => {
          if (disposed) return;
          try {
            const item = JSON.parse((event as MessageEvent).data) as MissionEvent;
            if (item.mission_id !== id || !Number.isInteger(item.sequence)) return;
            if (item.sequence > cursor + 1) {
              history(id, abort.signal).then(recorded => {
                if (!disposed) setEvents(old => mergeEvents(old, recorded.events, id));
              }).catch(() => { if (!disposed) setError("Activity history could not be reconciled. Reload to retry."); });
            }
            cursor = Math.max(cursor, item.sequence);
            setEvents(old => mergeEvents(old, [item], id));
            reconcile();
          } catch { setError("An activity event could not be read. Reload to reconcile history."); }
        });
      } catch (e) {
        if (!disposed) { setError((e as Error).message); setConnection("offline"); }
      }
    }
    start();
    return () => { disposed = true; generation.current++; abort.abort(); source?.close(); clearTimeout(timer); };
  }, [id, refresh]);
  return { detail, events, repository, error, connection, refresh };
}
