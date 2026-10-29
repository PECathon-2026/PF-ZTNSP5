"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

type HealthPhase = "checking" | "up" | "down";

export type HealthState = {
  phase: HealthPhase;
  health: HealthResponse | null;
  error: string | null;
};

export function useHealth(pollMs = 30000): HealthState & { retry: () => void } {
  const [state, setState] = useState<HealthState>({ phase: "checking", health: null, error: null });
  const [attempt, setAttempt] = useState(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    async function probe() {
      try {
        const health = await api.health(controller.signal);
        if (cancelled) return;
        setState({ phase: "up", health, error: null });
      } catch (error) {
        if (cancelled || controller.signal.aborted) return;
        setState({
          phase: "down",
          health: null,
          error: error instanceof Error ? error.message : "The backend did not respond.",
        });
      } finally {
        if (!cancelled && pollMs > 0) {
          timerRef.current = setTimeout(() => {
            if (!cancelled) setAttempt((value) => value + 1);
          }, pollMs);
        }
      }
    }

    setState((previous) => ({ ...previous, phase: "checking" }));
    void probe();

    return () => {
      cancelled = true;
      controller.abort();
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [attempt, pollMs]);

  return { ...state, retry };
}

export function ConnectionStatus() {
  const { phase, health, error, retry } = useHealth(30000);
  const label =
    phase === "checking" ? "Checking API" : phase === "up" ? "Backend connected" : "Backend offline";
  const detail =
    phase === "checking"
      ? "Contacting the local KAGE backend…"
      : phase === "up"
        ? `${health?.service ?? "kage-backend"} v${health?.version ?? "?"} · ${health?.active_missions_count ?? 0} active mission(s)`
        : (error ?? "The local API did not respond.");

  if (phase === "down") {
    return (
      <button type="button" className="header-health" onClick={retry} title={`${detail} Click to retry.`}>
        <span className="status-pip status-pip--unavailable" aria-hidden="true" />
        <span className="header-health-label">{label}</span>
      </button>
    );
  }

  return (
    <span className="header-health" role="status" title={detail}>
      <span
        className={`status-pip status-pip--${phase === "checking" ? "checking" : "responding"}`}
        aria-hidden="true"
      />
      <span className="header-health-label">{label}</span>
    </span>
  );
}

export function ReadinessProbe() {
  const { phase, health, error, retry } = useHealth(20000);

  const rows: { title: string; state: "ready" | "unknown" | "blocked"; detail: string }[] = [
    {
      title: "Application API",
      state: phase === "up" ? "ready" : phase === "down" ? "blocked" : "unknown",
      detail:
        phase === "checking"
          ? "Contacting the local backend…"
          : phase === "up"
            ? `Responding (service ${health?.service ?? "kage-backend"} v${health?.version ?? "?"}).`
            : (error ?? "No response from the local backend."),
    },
    {
      title: "Model connection",
      state: health ? (health.model_configured ? "ready" : "unknown") : "unknown",
      detail: health
        ? health.model_configured
          ? "A model endpoint is configured for the backend."
          : "No model credentials are configured, so agent reasoning cannot run."
        : "Backend unreachable — model readiness cannot be read.",
    },
    {
      title: "Execution environment",
      state: health ? (health.docker_available ? "ready" : "blocked") : "unknown",
      detail: health
        ? health.docker_available
          ? "Container runtime responded to the backend's readiness probe."
          : "Container runtime unavailable — restricted execution is blocked by preflight."
        : "Backend unreachable — execution readiness cannot be read.",
    },
    {
      title: "Storage",
      state: health ? (health.storage_ready ? "ready" : "blocked") : "unknown",
      detail: health
        ? health.storage_ready
          ? "Mission storage initialized."
          : "Mission storage is not ready."
        : "Backend unreachable — storage readiness cannot be read.",
    },
  ];

  return (
    <div className="readiness-list">
      {rows.map((row) => (
        <div className="readiness-row" key={row.title}>
          <span
            className={`status-pip ${
              row.state === "ready"
                ? "status-pip--responding"
                : row.state === "blocked"
                  ? "status-pip--unavailable"
                  : "status-pip--checking"
            }`}
            aria-hidden="true"
          />
          <div>
            <strong>{row.title}</strong>
            <p>{row.detail}</p>
          </div>
          <span className="readiness-label">
            {row.state === "ready" ? "READY" : row.state === "blocked" ? "BLOCKED" : "UNKNOWN"}
          </span>
        </div>
      ))}
      <div className="readiness-row">
        <span className="status-pip" aria-hidden="true" />
        <div>
          <strong>Repository type</strong>
          <p>Detected per repository when it is connected and preflighted.</p>
        </div>
        <span className="readiness-label">ON CONNECT</span>
        <button type="button" className="text-link" onClick={retry}>
          Recheck
        </button>
      </div>
    </div>
  );
}
