/** Serve Monaco locally so source inspection does not depend on a CDN. */
import { cp, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const root = new URL("../", import.meta.url);
await mkdir(new URL("public/monaco/", root), { recursive: true });
await rm(new URL("public/monaco/vs/", root), { recursive: true, force: true });
await cp(fileURLToPath(new URL("node_modules/monaco-editor/min/vs/", root)),
  fileURLToPath(new URL("public/monaco/vs/", root)), { recursive: true });
