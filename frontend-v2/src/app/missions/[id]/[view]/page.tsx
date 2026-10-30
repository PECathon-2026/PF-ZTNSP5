import { Suspense } from "react";
import { notFound } from "next/navigation";
import { MissionShell } from "@/components/mission-shell";

export default async function MissionPage({ params }: { params: Promise<{ id: string; view: string }> }) {
  const { id, view } = await params;
  if (!/^[a-zA-Z0-9_-]+$/.test(id) || !["workspace", "graph", "review"].includes(view)) notFound();
  return <Suspense fallback={<p>Opening mission…</p>}><MissionShell key={id} id={id} view={view}/></Suspense>;
}
