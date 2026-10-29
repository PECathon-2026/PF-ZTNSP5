"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { Mission, MissionDetail, MissionEvent, MissionTask, AcceptanceCriterion, MissionReport, MissionStatus } from "./types";

export type MissionsState = {
  missions: Mission[];
  loading: boolean;
  error: string | null;
  reload: () => void;
};

const MISSION_POLL_MS = 4000;

export function useMissions(): MissionsState {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    api
      .listMissions(controller.signal)
      .then((data) => {
        if (controller.signal.aborted) return;
        setMissions(data);
        setError(null);
      })
      .catch((caught) => {
        if (controller.signal.aborted) return;
        if (caught instanceof DOMException && caught.name === "AbortError") return;
        setError(caught instanceof ApiError ? caught.detail : "Missions could not be loaded.");
        setMissions([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [attempt]);

  return { missions, loading, error, reload };
}

export type MissionDetailState = {
  detail: MissionDetail | null;
  mission: Mission | null;
  criteria: AcceptanceCriterion[];
  tasks: MissionTask[];
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => void;
};

export function useMissionDetail(missionId: string): MissionDetailState {
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const [mission, setMission] = useState<Mission | null>(null);
  const [criteria, setCriteria] = useState<AcceptanceCriterion[]>([]);
  const [tasks, setTasks] = useState<MissionTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      const controller = new AbortController();
      try {
        const detail = await api.getMission(missionId, controller.signal);
        if (cancelled) return;
        setDetail(detail);
        setMission(detail.mission);
        setCriteria(detail.criteria ?? []);
        setTasks(detail.tasks ?? []);
        setNotFound(false);
        setError(null);
      } catch (caught) {
        if (cancelled) return;
        if (caught instanceof ApiError && caught.status === 404) {
          setNotFound(true);
          setMission(null);
          setError(null);
        } else if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof ApiError ? caught.detail : "Mission status could not be read.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          timer = setTimeout(tick, MISSION_POLL_MS);
        }
      }
      controller.abort();
    }

    setLoading(true);
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [missionId, attempt]);

  return { detail, mission, criteria, tasks, loading, notFound, error, reload };
}

export type MissionEventsState = {
  events: MissionEvent[];
  phase: "connecting" | "live" | "error";
  error: string | null;
  lastSequence: number;
};

export function useMissionEvents(missionId: string, enabled = true, onEvent?: () => void): MissionEventsState {
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [phase, setPhase] = useState<MissionEventsState["phase"]>("connecting");
  const [error, setError] = useState<string | null>(null);
  const callback = useRef(onEvent);
  useEffect(() => { callback.current = onEvent; }, [onEvent]);

  useEffect(() => {
    if (!enabled) return;
    setEvents([]);
    setPhase("connecting");
    setError(null);
    let cursor = 0;
    let reconcile: ReturnType<typeof setTimeout> | undefined;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let stream: EventSource | null = null;
    let disposed = false;
    let failures = 0;
    const receive = (message: MessageEvent<string>) => {
      try {
        const incoming = JSON.parse(message.data) as Partial<MissionEvent>;
        if (incoming.mission_id !== missionId || !Number.isSafeInteger(incoming.sequence) ||
            !incoming.sequence || incoming.sequence <= cursor || typeof incoming.event_type !== "string") return;
        cursor = incoming.sequence;
        failures = 0;
        const event: MissionEvent = {
          sequence: cursor, mission_id: missionId, event_type: incoming.event_type,
          source: incoming.source ?? "CONTROLLER", task_id: incoming.task_id ?? null,
          candidate_id: incoming.candidate_id ?? null, evidence_ids: incoming.evidence_ids ?? [],
          display_payload: incoming.display_payload ?? {}, created_at: incoming.created_at ?? "",
        };
        setEvents((previous) => [...previous, event]);
        if (!reconcile) {
          reconcile = setTimeout(() => { reconcile = undefined; callback.current?.(); }, 250);
        }
      } catch {
        setError("An event could not be decoded. Mission details continue to refresh.");
      }
    };
    function connect() {
      if (disposed) return;
      // Reopen explicitly at the last accepted sequence, including across proxy disconnects.
      const connection = new EventSource(`/api/missions/${encodeURIComponent(missionId)}/events?after=${cursor}`);
      stream = connection;
      connection.onopen = () => { setPhase("live"); setError(null); };
      connection.addEventListener("mission", receive);
      connection.onerror = () => {
        connection.close(); connection.removeEventListener("mission", receive);
        if (disposed) return;
        setPhase("error");
        setError("Event connection interrupted. Reconnecting with replay; mission details keep refreshing.");
        retry = setTimeout(connect, Math.min(1000 * 2 ** failures++, 10000));
      };
    }
    connect();
    return () => {
      disposed = true;
      stream?.removeEventListener("mission", receive);
      stream?.close();
      if (retry) clearTimeout(retry);
      if (reconcile) clearTimeout(reconcile);
    };
  }, [missionId, enabled]);

  const lastSequence = events.length > 0 ? events[events.length - 1].sequence : 0;
  return { events, phase, error, lastSequence };
}

export const TERMINAL_STATUSES: MissionStatus[] = ["APPLIED", "REJECTED", "CANCELLED", "INTERRUPTED"];

export function isTerminalStatus(status: MissionStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export type MissionReportState = {
  report: MissionReport | null;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => void;
};

export function useMissionReport(missionId: string): MissionReportState {
  const [report, setReport] = useState<MissionReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      const controller = new AbortController();
      try {
        const fetched = await api.missionReport(missionId, controller.signal);
        if (cancelled) return;
        setReport(fetched);
        setNotFound(false);
        setError(null);
      } catch (caught) {
        if (cancelled) return;
        if (caught instanceof ApiError && caught.status === 404) {
          setNotFound(true);
          setReport(null);
          setError(null);
        } else if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setError(caught instanceof ApiError ? caught.detail : "The evidence report could not be read.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
          timer = setTimeout(tick, MISSION_POLL_MS);
        }
      }
      controller.abort();
    }

    setLoading(true);
    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [missionId, attempt]);

  return { report, loading, notFound, error, reload };
}
