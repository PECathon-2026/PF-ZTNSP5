import dynamic from "next/dynamic";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Monaco, MonacoDiffEditor } from "@monaco-editor/react";

const Editor = dynamic(
  () =>
    import("@monaco-editor/react").then((mod) => mod.Editor),
  { ssr: false, loading: () => null },
);
const DiffEditor = dynamic(() => import("@monaco-editor/react").then((mod) => mod.DiffEditor), { ssr: false, loading: () => <p className="mono">Opening comparison…</p> });

function configureTheme(monaco: Monaco) {
  monaco.editor.defineTheme("kage-sumi", { base: "vs-dark", inherit: true,
    rules: [{ token: "keyword", foreground: "D0A659" }, { token: "string", foreground: "9AB6A3" }, { token: "comment", foreground: "929B9D" }, { token: "type", foreground: "C6B393" }],
    colors: { "editor.background": "#101419", "editor.foreground": "#E7E3DA", "editorLineNumber.foreground": "#9A9C96", "editorCursor.foreground": "#E8C66A", "editor.selectionBackground": "#73501D", "editor.lineHighlightBackground": "#191E25" },
  });
}

type ForgeEditorProps = {
  value: string;
  language: string;
  height?: string;
  line?: number;
};

export function ForgeEditor({ value, language, height = "100%", line }: ForgeEditorProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return (
    <Editor
      theme="kage-sumi"
      language={language}
      value={value}
      line={line}
      height={height}
      width="100%"
      options={{
        minimap: { enabled: false },
        lineNumbers: "on",
        wordWrap: "on",
        readOnly: true,
        fontFamily: "'JetBrains Mono', 'Cascadia Code', monospace",
        fontSize: 13,
      }}
      beforeMount={configureTheme}
    />
  );
}

export function ForgeDiffEditor({ original, modified, language }: { original: string; modified: string; language: string }) {
  const instance = useRef<MonacoDiffEditor | null>(null);
  useLayoutEffect(() => () => {
    const editor = instance.current;
    if (!editor) return;
    const models = editor.getModel();
    // Detach before disposal; the wrapper's passive cleanup otherwise disposes
    // models while newer Monaco diff widgets still hold their subscriptions.
    editor.setModel(null);
    models?.original.dispose();
    models?.modified.dispose();
    instance.current = null;
  }, []);
  return <DiffEditor original={original} modified={modified} language={language} theme="kage-sumi" height="100%" beforeMount={configureTheme} onMount={(editor) => { instance.current = editor; }}
    options={{ readOnly: true, originalEditable: false, renderSideBySide: true, enableSplitViewResizing: true, minimap: { enabled: false }, fontFamily: "'JetBrains Mono', monospace", fontSize: 12, automaticLayout: true, ignoreTrimWhitespace: false }} />;
}
