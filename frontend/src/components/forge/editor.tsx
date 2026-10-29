import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const Editor = dynamic(
  () =>
    import("@monaco-editor/react").then((mod) => mod.Editor),
  { ssr: false, loading: () => null },
);

type ForgeEditorProps = {
  value: string;
  language: string;
  height?: string;
};

export function ForgeEditor({ value, language, height = "100%" }: ForgeEditorProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return (
    <Editor
      theme="vs-dark"
      language={language}
      value={value}
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
      beforeMount={(monaco) => {
        monaco.editor.defineTheme("kage-sumi", {
          base: "vs-dark",
          inherit: true,
          rules: [{ token: "", foreground: "a6b8c4", background: "14171c" }],
        });
        monaco.editor.setTheme("kage-sumi");
      }}
    />
  );
}
