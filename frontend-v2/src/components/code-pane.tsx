"use client";

import { useEffect, useRef, useState } from "react";
import Editor, { loader } from "@monaco-editor/react";
import type { DiffEditorProps } from "@monaco-editor/react";
import type { editor } from "monaco-editor";
import { api } from "@/lib/api";
import { Empty } from "./ui";

loader.config({ paths: { vs: "/monaco/vs" } });
function revealLine(instance: editor.IStandaloneCodeEditor | null | undefined, requested?: number) {
  if (!instance || !requested) return;
  const model = instance.getModel();
  if (!model || model.isDisposed()) return;
  const line = Math.min(requested, model.getLineCount());
  instance.revealLineInCenter(line);
  instance.setPosition({ lineNumber: line, column: 1 });
}

function ManagedDiff(props: DiffEditorProps & { line?: number }) {
  const container = useRef<HTMLDivElement>(null);
  const currentWidget = useRef<editor.IStandaloneDiffEditor | null>(null);
  const requestedLine = useRef(props.line);
  requestedLine.current = props.line;
  const [error, setError] = useState("");
  const { original = "", modified = "", language = "plaintext" } = props;
  useEffect(() => {
    let cancelled = false;
    let widget: editor.IStandaloneDiffEditor | undefined;
    let before: editor.ITextModel | undefined;
    let after: editor.ITextModel | undefined;
    loader.init().then(monaco => {
      if (cancelled || !container.current) return;
      widget = monaco.editor.createDiffEditor(container.current, {
        readOnly: true, originalEditable: false, automaticLayout: true, theme: "vs-dark",
        minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false,
        padding: { top: 18 }, renderSideBySide: true,
      });
      before = monaco.editor.createModel(original, language);
      after = monaco.editor.createModel(modified, language);
      widget.setModel({ original: before, modified: after });
      currentWidget.current = widget;
      revealLine(widget.getModifiedEditor(), requestedLine.current);
    }).catch(() => { if (!cancelled) setError("Editor unavailable. Choose Plain text to inspect the source."); });
    return () => {
      cancelled = true;
      // Explicit ownership: detach models BEFORE disposing the widget or models.
      widget?.setModel(null);
      widget?.dispose();
      before?.dispose();
      after?.dispose();
      currentWidget.current = null;
    };
  }, [original, modified, language]);
  useEffect(() => { revealLine(currentWidget.current?.getModifiedEditor(), props.line); }, [props.line]);
  return <>{error && <p role="alert">{error}</p>}<div ref={container} style={{ width: "100%", height: "100%", minHeight: 200 }}/></>;
}
export function CodePane({ missionId, candidateId, path, line }: { missionId: string; candidateId: string; path: string; line?: number }) {
  const [mode, setMode] = useState("diff");
  const [data, setData] = useState<{ before: string; after: string; beforeMissing: boolean; afterMissing: boolean } | null>(null);
  const [error, setError] = useState("");
  const [plain, setPlain] = useState(false);
  const singleEditor = useRef<editor.IStandaloneCodeEditor | null>(null);
  useEffect(() => { revealLine(singleEditor.current, line); }, [line, mode, data]);
  useEffect(() => {
    if (!path) { setData(null); setError(""); return; }
    const abort = new AbortController(); setData(null); setError("");
    async function read(url: string) {
      // A missing side of a diff is a legitimate addition/deletion, other errors are not.
      const res = await fetch(`/api/backend${url}`, { signal: abort.signal, cache: "no-store" });
      if (res.status === 404) return { content: "", missing: true };
      if (!res.ok) throw new Error((await res.json()).detail || "Snapshot could not be read");
      return { ...(await res.json()) as { content: string }, missing: false };
    }
    const base = `/missions/${missionId}`;
    const query = `?path=${encodeURIComponent(path)}`;
    Promise.all([read(`${base}/baseline/file${query}`), candidateId ? read(`${base}/candidates/${candidateId}/file${query}`) : read(`${base}/baseline/file${query}`)])
      .then(([before, after]) => setData({ before: before.content, after: after.content, beforeMissing: before.missing, afterMissing: after.missing }))
      .catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [missionId, candidateId, path]);
  const language = path.endsWith(".py") ? "python" : path.endsWith(".json") ? "json" : path.endsWith(".md") ? "markdown" : "plaintext";
  const options = { readOnly: true, minimap: { enabled: false }, fontSize: 13, scrollBeyondLastLine: false, automaticLayout: true, padding: { top: 18 }, renderSideBySide: true };
  return <section className="code-pane">
    <div className="code-toolbar"><span className="mono">{path || "Select a file"}{line ? `:${line}` : ""}</span><div className="segmented">{["diff", "candidate", "baseline"].map(tab => <button key={tab} className={mode === tab ? "selected" : ""} onClick={() => setMode(tab)}>{tab}</button>)}</div><button className="quiet small-text" onClick={() => setPlain(p => !p)}>{plain ? "Editor" : "Plain text"}</button></div>
    {error ? <div className="error-banner" role="alert">{error}</div> : !path ? <Empty title="Your canvas is ready">Select a file to inspect source or compare a candidate.</Empty> : !data ? <Empty title="Reading frozen source…"/> : <>
      <div className="source-caption">{mode === "diff" ? "Frozen baseline → selected candidate" : mode === "baseline" ? "Frozen baseline · read only" : "Selected candidate · read only"}{data.beforeMissing && " · New file"}{data.afterMissing && " · Deleted file"}{line && ` · Finding at line ${line}`}</div>
      <div className="editor-area">{plain ? <div className={mode === "diff" ? "plain-diff" : ""}>{mode !== "candidate" && <pre>{data.before || "(empty or absent)"}</pre>}{mode !== "baseline" && <pre>{data.after || "(empty or absent)"}</pre>}</div> : mode === "diff" ? <ManagedDiff key={`${candidateId}-${path}`} original={data.before} modified={data.after} language={language} line={line} theme="vs-dark" options={options}/> : <Editor value={mode === "baseline" ? data.before : data.after} language={language} theme="vs-dark" options={options} onMount={instance => { singleEditor.current = instance; revealLine(instance, line); }}/>}</div>
    </>}
  </section>;
}

export function UnifiedDiff({ missionId, candidateId }: { missionId: string; candidateId: string }) {
  const [diff, setDiff] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    const abort = new AbortController(); setDiff(""); setError("");
    if (candidateId) api<{ unified_diff: string }>(`/missions/${missionId}/candidates/${candidateId}/diff`, undefined, abort.signal)
      .then(d => setDiff(d.unified_diff)).catch(e => { if (!abort.signal.aborted) setError(e.message); });
    return () => abort.abort();
  }, [missionId, candidateId]);
  return error ? <p className="error-banner">{error}</p> : <pre className="unified-diff">{diff ? diff.split("\n").map((line, i) => <span key={i} className={line.startsWith("+") ? "added" : line.startsWith("-") ? "removed" : line.startsWith("@@") ? "hunk" : ""}>{line}{"\n"}</span>) : "No candidate diff available yet."}</pre>;
}
