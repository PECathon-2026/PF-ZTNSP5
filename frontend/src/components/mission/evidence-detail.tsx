"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EvidenceDetail as EvidenceRecord } from "@/lib/types";
import { Modal } from "./modal";
import "./mission-tools.css";

export function EvidenceDetail({ missionId, evidenceId, onClose }: { missionId: string; evidenceId: string; onClose: () => void }) {
  const [record, setRecord] = useState<EvidenceRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    api.evidenceDetail(missionId, evidenceId, controller.signal)
      .then((data) => { if (!controller.signal.aborted) setRecord(data); })
      .catch((caught) => { if (!controller.signal.aborted) setError(caught instanceof Error ? caught.message : "Evidence could not be read."); });
    return () => controller.abort();
  }, [missionId, evidenceId]);
  return <Modal title="Evidence artifact" onClose={onClose}>
    <p className="mono muted">{evidenceId}</p>
    {error ? <p role="alert" className="field-error">{error}</p> : !record ? <p role="status">Reading recorded output…</p> : <>
      <p className="mono">{record.kind} · {record.source} · exit {record.exit_code ?? "not recorded"} · {record.duration_ms} ms</p>
      <p className="mission-fingerprint mono">Candidate {record.candidate_id}<br />{record.fingerprint}</p>
      <h3>Command</h3><pre className="mission-output">{record.command.join(" ") || "No command recorded"}</pre>
      <h3>Standard output</h3><pre className="mission-output">{record.stdout || "No stdout recorded"}</pre>
      <h3>Standard error</h3><pre className="mission-output">{record.stderr || "No stderr recorded"}</pre>
      <details><summary>Recorded metadata</summary><pre className="mission-output">{JSON.stringify(record.metadata, null, 2)}</pre></details>
      <p className="muted">Output is bounded by the backend to 12,000 characters per stream.</p>
    </>}
  </Modal>;
}
