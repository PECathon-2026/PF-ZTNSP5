/** Same-origin, streaming proxy to the configured local backend. */
import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, context: Context) {
  const { path } = await context.params;
    if (!path.length || !["missions", "repositories", "health", "model-config"].includes(path[0]) ||
      path.some(part => !/^[a-zA-Z0-9_-]+$/.test(part))) {
    return Response.json({ detail: "Unknown backend resource" }, { status: 404 });
  }
  // Browsers must send mutation requests from this app, not a third-party origin.
  const origin = request.headers.get("origin");
  if (request.method !== "GET" && origin && origin !== request.nextUrl.origin &&
      origin !== `${request.nextUrl.protocol}//${request.headers.get("host")}`) {
    return Response.json({ detail: "Cross-origin action refused" }, { status: 403 });
  }
  const base = (process.env.KAGE_BACKEND_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const headers = new Headers({ "Content-Type": "application/json" });
  const cursor = request.headers.get("last-event-id");
  if (cursor) headers.set("Last-Event-ID", cursor);
  try {
    const response = await fetch(`${base}/api/${path.join("/")}${request.nextUrl.search}`, {
      method: request.method, headers, cache: "no-store", signal: request.signal,
      body: request.method === "GET" ? undefined : await request.text(),
    });
    const outgoing = new Headers({ "Cache-Control": "no-cache, no-transform" });
    for (const name of ["content-type", "content-disposition", "x-accel-buffering"]) {
      const value = response.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return Response.json({ detail: "Backend unavailable. Start the KAGE backend on port 8000." }, { status: 502 });
  }
}
export const GET = forward;
export const POST = forward;
