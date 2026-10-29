"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { PreflightResult, RepositoryConnectResponse, StoredRepository } from "@/lib/types";
import { basename, preflightMeta, shortPath } from "@/lib/status";
import { buildTree, type TreeNode } from "@/lib/tree";
import {
  findRepository,
  getActiveRepositoryId,
  readRepositories,
  saveRepository,
  setActiveRepositoryId,
} from "@/lib/repository-session";

type RepositoryPanelProps = {
  connected: StoredRepository | null;
  onConnected: (repository: StoredRepository | null) => void;
  focusRequest: number;
};

function TreePreview({ tree, fileCount }: { tree: TreeNode; fileCount: number }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [filter, setFilter] = useState("");

  const visiblePaths = useMemo(() => {
    if (!filter.trim()) return null;
    const needle = filter.trim().toLowerCase();
    return new Set(
      tree.children.flatMap((child) => flatten(child)).filter((path) => path.toLowerCase().includes(needle)),
    );
  }, [filter, tree]);

  function flatten(node: TreeNode): string[] {
    if (node.file) return [node.path];
    return node.children.flatMap((child) => flatten(child));
  }

  function toggle(path: string) {
    setExpanded((previous) => ({ ...previous, [path]: !previous[path] }));
  }

  function renderNode(node: TreeNode, depth: number): React.ReactNode {
    if (visiblePaths && !visiblePaths.has(node.path) && node.file) return null;
    if (visiblePaths && !node.file) {
      const hasVisible = node.children.some((child) => flatten(child).some((path) => visiblePaths.has(path)));
      if (!hasVisible && !visiblePaths.has(node.path)) return null;
    }

    if (node.file) {
      if (visiblePaths && !visiblePaths.has(node.path)) return null;
      return (
        <li key={node.path} className="tree-file" style={{ paddingLeft: `${depth * 14 + 8}px` }}>
          <span className="tree-glyph" aria-hidden="true">
            ▪
          </span>
          <span className="tree-name">{node.name}</span>
        </li>
      );
    }

    const open = expanded[node.path] ?? depth < 1;
    return (
      <li key={node.path} className="tree-dir">
        <button
          type="button"
          className="tree-toggle"
          style={{ paddingLeft: `${depth * 14 + 4}px` }}
          aria-expanded={open}
          onClick={() => toggle(node.path)}
        >
          <span className="tree-glyph" aria-hidden="true">
            {open ? "▾" : "▸"}
          </span>
          <span className="tree-name">{node.name}</span>
        </button>
        {open && (
          <ul className="tree-group">
            {node.children.map((child) => renderNode(child, depth + 1))}
          </ul>
        )}
      </li>
    );
  }

  return (
    <div className="tree-preview">
      <label className="visually-hidden" htmlFor="tree-filter">
        Filter files
      </label>
      <input
        id="tree-filter"
        className="input tree-filter"
        type="search"
        placeholder="Filter file names…"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
      />
      <div className="tree-scroll" role="region" aria-label={`Repository files (${fileCount})`}>
        <ul className="tree-list">
          {tree.children.map((child) => renderNode(child, 0))}
        </ul>
        {tree.children.length === 0 && <p className="tree-empty">No files are visible inside this repository.</p>}
      </div>
    </div>
  );
}

export function RepositoryPanel({ connected, onConnected, focusRequest }: RepositoryPanelProps) {
  const [path, setPath] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tree, setTree] = useState<string[] | null>(null);
  const [treeError, setTreeError] = useState<string | null>(null);
  const [known, setKnown] = useState<StoredRepository[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setKnown(readRepositories());
  }, []);

  useEffect(() => {
    if (focusRequest > 0) inputRef.current?.focus();
  }, [focusRequest]);

  useEffect(() => {
    if (!connected) {
      setTree(null);
      setTreeError(null);
      return;
    }
    const controller = new AbortController();
    setTreeError(null);
    api
      .repositoryTree(connected.repository_id, controller.signal)
      .then((paths) => {
        if (!controller.signal.aborted) setTree(paths);
      })
      .catch((caught) => {
        if (controller.signal.aborted) return;
        setTree(null);
        setTreeError(
          caught instanceof ApiError
            ? caught.status === 404
              ? "This repository session is no longer registered (the backend restarted). Reconnect it to continue."
              : caught.detail
            : "The repository tree could not be loaded.",
        );
      });
    return () => controller.abort();
  }, [connected]);

  async function connect(rawPath: string, repository?: StoredRepository) {
    const target = rawPath.trim();
    if (!target && !repository) {
      setError("Enter the local path of the repository you want the guild to work on.");
      inputRef.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result: RepositoryConnectResponse = await api.connectRepository(repository?.path ?? target);
      const stored: StoredRepository = {
        repository_id: result.repository_id,
        name: result.name,
        path: result.path,
        fingerprint: result.fingerprint,
        preflight: result.preflight,
        connected_at: Date.now(),
      };
      saveRepository(stored);
      setActiveRepositoryId(stored.repository_id);
      setKnown(readRepositories());
      setPath("");
      onConnected(stored);
    } catch (caught) {
      const detail =
        caught instanceof ApiError
          ? caught.status === 403
            ? "That path is outside the allowed repository boundary."
            : caught.status === 404
              ? "No such directory exists on the machine running the backend."
              : caught.detail
          : "The repository could not be connected.";
      setError(detail);
      if (repository) onConnected(null);
    } finally {
      setBusy(false);
    }
  }

  const preflight: PreflightResult | null = connected?.preflight ?? null;
  const meta = preflight ? preflightMeta(preflight.status) : null;
  const previewTree = useMemo(() => buildTree(tree ?? []), [tree]);

  return (
    <section className="panel setup-panel" aria-labelledby="repo-title">
      <div className="panel-head">
        <span className="panel-title">01 · SOURCE</span>
        {connected && meta && (
          <span className="status" data-tone={meta.tone}>
            {meta.glyph} {meta.label}
          </span>
        )}
      </div>

      <div className="setup-panel__body">
        <h2 id="repo-title">The repository</h2>
        <p className="muted">
          Point the guild at a local directory. The backend validates the path, applies its exclusion
          manifest, and runs preflight reconnaissance before anything is allowed to run.
        </p>

        <form
          className="repo-connect"
          onSubmit={(event) => {
            event.preventDefault();
            void connect(path);
          }}
        >
          <label htmlFor="repository-path">Local repository path</label>
          <div className="repo-connect__row">
            <input
              id="repository-path"
              ref={inputRef}
              className="input mono"
              type="text"
              spellCheck={false}
              autoComplete="off"
              placeholder="/home/you/projects/my-app"
              value={path}
              onChange={(event) => setPath(event.target.value)}
              aria-describedby="repository-hint"
              aria-invalid={Boolean(error)}
              disabled={busy}
            />
            <button className="btn btn--primary" type="submit" disabled={busy}>
              {busy ? <span className="btn-spinner" aria-hidden="true" /> : null}
              {busy ? "Connecting" : connected ? "Reconnect" : "Connect"}
            </button>
          </div>
          <small id="repository-hint" className={error ? "field-error" : "field-hint"} role={error ? "alert" : undefined}>
            {error ?? "Paths are validated by the backend; this page never reads files directly."}
          </small>
        </form>

        {known.length > 0 && (
          <div className="known-repos">
            <p className="field-label">Previously connected</p>
            <ul>
              {known.map((repository) => (
                <li key={repository.repository_id}>
                  <button
                    type="button"
                    className={`known-repo ${connected?.repository_id === repository.repository_id ? "is-active" : ""}`}
                    onClick={() => void connect("", repository)}
                    disabled={busy}
                  >
                    <span className="known-repo__name">{repository.name}</span>
                    <span className="known-repo__path mono">{shortPath(repository.path, 2)}</span>
                    {connected?.repository_id === repository.repository_id && (
                      <span className="status" data-tone="gold">
                        ACTIVE
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {connected && (
          <div className="repo-facts">
            <dl className="meta-grid">
              <div className="meta-item">
                <dt>Repository</dt>
                <dd>{connected.name}</dd>
              </div>
              <div className="meta-item">
                <dt>Path</dt>
                <dd className="mono" title={connected.path}>
                  {shortPath(connected.path, 2)}
                </dd>
              </div>
              <div className="meta-item">
                <dt>Project profile</dt>
                <dd className="mono">{preflight?.detected_profile ?? "—"}</dd>
              </div>
              <div className="meta-item">
                <dt>Included files</dt>
                <dd>{preflight ? preflight.file_count.toLocaleString() : "—"}</dd>
              </div>
              <div className="meta-item">
                <dt>Excluded</dt>
                <dd>{preflight ? preflight.excluded_count.toLocaleString() : "—"}</dd>
              </div>
              <div className="meta-item">
                <dt>Local modifications</dt>
                <dd>{preflight ? (preflight.existing_modifications ? "Detected" : "None") : "—"}</dd>
              </div>
            </dl>

            <p className="fingerprint mono" title={connected.fingerprint}>
              FINGERPRINT {connected.fingerprint.slice(0, 16)}…
            </p>

            {preflight && (preflight.warnings.length > 0 || preflight.blockers.length > 0) && (
              <ul className="preflight-notes">
                {preflight.blockers.map((blocker) => (
                  <li key={blocker} className="preflight-note preflight-note--blocker">
                    <span aria-hidden="true">×</span>
                    <span>{blocker}</span>
                  </li>
                ))}
                {preflight.warnings.map((warning) => (
                  <li key={warning} className="preflight-note preflight-note--warning">
                    <span aria-hidden="true">!</span>
                    <span>{warning}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {connected && treeError && (
          <div className="state-block state-block--error" role="alert">
            <span className="state-mark" aria-hidden="true">
              ×
            </span>
            <h3>Repository unavailable</h3>
            <p>{treeError}</p>
            <button type="button" className="btn btn--ghost" onClick={() => void connect("", connected)}>
              Reconnect repository
            </button>
          </div>
        )}

        {connected && !treeError && tree === null && (
          <div className="state-block" aria-busy="true">
            <span className="spinner" aria-hidden="true" />
            <p>Reading the approved file tree…</p>
          </div>
        )}

        {connected && !treeError && tree !== null && (
          <TreePreview tree={previewTree} fileCount={tree.length} />
        )}

        {!connected && (
          <div className="state-block state-block--inline">
            <span className="state-mark" aria-hidden="true">
              影
            </span>
            <h3>No repository connected</h3>
            <p>
              Enter a local path above. The backend will preflight it and return the file tree this
              panel can show.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

export function restoreActiveRepository(): StoredRepository | null {
  const activeId = getActiveRepositoryId();
  if (!activeId) return null;
  const found = findRepository(activeId);
  return found ?? null;
}

export function basenameOf(path: string): string {
  return basename(path);
}
