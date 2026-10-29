"use client";

import { useMemo, useState } from "react";
import { buildTree, type TreeNode } from "@/lib/tree";
import { fileGlyph } from "@/lib/status";

type ExplorerProps = {
  paths: string[];
  repositoryHint: string | null;
  onOpen: (path: string) => void;
  error: string | null;
  onRetry: () => void;
};

export function Explorer({ paths, repositoryHint, onOpen, error, onRetry }: ExplorerProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const tree = useMemo(() => buildTree(paths), [paths]);

  function render(node: TreeNode): React.ReactNode {
    if (node.file) {
      return (
        <li key={node.path} className="forge-tree__file">
          <span className="forge-tree__glyph" aria-hidden="true">
            {fileGlyph(node.path)}
          </span>
          <button
            type="button"
            className="forge-tree__name"
            title={node.path}
            onClick={() => onOpen(node.path)}
          >
            {node.name}
          </button>
        </li>
      );
    }
    const open = expanded[node.path] ?? false;
    return (
      <li key={node.path} className="forge-tree__dir">
        <button
          type="button"
          className="forge-tree__toggle"
          aria-expanded={open}
          onClick={() => setExpanded((previous) => ({ ...previous, [node.path]: !open }))}
        >
          <span className="forge-tree__glyph" aria-hidden="true">
            {open ? "▾" : "▸"}
          </span>
          {node.name}
        </button>
        {open && (
          <ul className="forge-tree__group">
            {node.children.map((child) => render(child))}
          </ul>
        )}
      </li>
    );
  }

  return (
    <section className="panel forge-explorer" aria-labelledby="explorer-title">
      <div className="panel-head">
        <span className="panel-title" id="explorer-title">
          REPOSITORY
        </span>
        <span className="forge-explorer__count mono">{paths.length} files</span>
      </div>
      {error && (
        <div className="state-block state-block--error" role="alert" style={{ padding: "0.6rem 0.7rem" }}>
          <span className="state-mark" aria-hidden="true">
            ×
          </span>
          <h3 style={{ margin: "0 0 0.3rem", fontSize: "var(--text-xs)" }}>Repository unavailable</h3>
          <p style={{ margin: 0, fontSize: "var(--text-xs)" }}>{error}</p>
          <button type="button" className="btn btn--ghost btn--sm" style={{ marginTop: "0.4rem" }} onClick={onRetry}>
            Reconnect repository
          </button>
        </div>
      )}
      <div className="forge-explorer__hint mono" title={repositoryHint ?? ""}>
        {repositoryHint ?? "No repository bound to this mission."}
      </div>
      <div className="forge-tree__scroll" role="region" aria-label="Repository files">
        <ul className="forge-tree__list">        {tree.children.map((child: TreeNode) => render(child))}</ul>
        {tree.children.length === 0 && !error && <p className="forge-tree__empty">No files exposed by preflight.</p>}
      </div>
    </section>
  );
}
