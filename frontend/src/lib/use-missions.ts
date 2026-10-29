"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api";
import type { Mission, MissionEvent, MissionTask, AcceptanceCriterion, MissionReport, MissionStatus } from "./types";

export type MissionsState = {
  missions: Mission[];
  loading: boolean;
  error: string | null;
  reload: () => void;
};

const MISSION_POLL_MS = 4000;
const EVENTS_POLL_MS = 3000;

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
  mission: Mission | null;
  criteria: AcceptanceCriterion[];
  tasks: MissionTask[];
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => void;
};

export function useMissionDetail(missionId: string): MissionDetailState {
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

  return { mission, criteria, tasks, loading, notFound, error, reload };
}

export type MissionEventsState = {
  events: MissionEvent[];
  phase: "connecting" | "live" | "error";
  error: string | null;
  lastSequence: number;
};

export function useMissionEvents(missionId: string, enabled = true): MissionEventsState {
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [phase, setPhase] = useState<MissionEventsState["phase"]>("connecting");
  const [error, setError] = useState<string | null>(null);
  const cursor = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let failureStreak = 0;

    async function tick() {
      const controller = new AbortController();
      try {
        const batch = await api.missionEvents(missionId, cursor.current, controller.signal);
        if (cancelled) return;
        if (batch.length > 0) {
          cursor.current = Math.max(...batch.map((event) => event.sequence), cursor.current);
          setEvents((previous) => {
            const seen = new Set(previous.map((event) => event.sequence));
            const merged = previous.concat(batch.filter((event) => !seen.has(event.sequence)));
            merged.sort((a, b) => a.sequence - b.sequence);
            return merged;
          });
        } else {
          setEvents((previous) => {
            if (previous.length === 0 && cursor.current === 0) return previous;
            return previous;
          });
        }
        failureStreak = 0;
        setPhase("live");
        setError(null);
      } catch (caught) {
        if (cancelled) return;
        failureStreak += 1;
        if (failureStreak >= 2) {
          setPhase("error");
          setError(
            caught instanceof ApiError
              ? caught.detail
              : "The event stream could not be read. The mission view keeps polling.",
          );
        }
      } finally {
        if (!cancelled) timer = setTimeout(tick, EVENTS_POLL_MS);
      }
      controller.abort();
    }

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
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
