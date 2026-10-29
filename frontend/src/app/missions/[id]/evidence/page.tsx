import type { Metadata } from "next";
import { EvidenceScreen } from "@/components/evidence/evidence-screen";
import "./evidence.css";

export const metadata: Metadata = { title: "Evidence & approval" };

export default async function EvidencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <EvidenceScreen missionId={id} />;
}
