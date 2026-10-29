"use client";

import { useCallback, useEffect, useState } from "react";
import { classifyHealth } from "@/lib/mission-draft";

type Health = { state: "checking" | "unavailable" | "responding"; label: string; detail: string };

export function HealthStatus({ detailed = false }: { detailed?: boolean }) {
  const [health, setHealth] = useState<Health>({ state: "checking", label: "Checking API", detail: "Checking for a local backend…" });
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    // The current repository has no API route. A response is connectivity only, never model or execution readiness.
    fetch("/api/health", { signal: controller.signal, cache: "no-store", headers: { Accept: "application/json" } })
      .then(async (response) => {
        const contentType = response.headers.get("content-type") ?? "";
        const body = response.ok && contentType.toLowerCase().includes("application/json") ? await response.json() : null;
        return classifyHealth(response, contentType, body);
      })
      .then((result) => { if (!controller.signal.aborted) setHealth(result); })
      .catch(() => { if (!controller.signal.aborted) setHealth({ state: "unavailable", label: "API unavailable", detail: "The local API did not respond. Start the backend, then retry." }); })
      .finally(() => clearTimeout(timeout));
    return () => { controller.abort(); clearTimeout(timeout); };
  }, [attempt]);

  if (detailed) return (
    <div className="readiness-row">
      <span className={`status-pip status-pip--${health.state}`} aria-hidden="true" />
      <div><strong>Application API</strong><p>{health.detail}</p></div>
      <span className="readiness-label">{health.label}</span>
      <button type="button" className="text-action" onClick={retry}>Retry</button>
    </div>
  );

  return <span className="header-health" role="status"><span className={`status-pip status-pip--${health.state}`} aria-hidden="true" />{health.label}</span>;
}
