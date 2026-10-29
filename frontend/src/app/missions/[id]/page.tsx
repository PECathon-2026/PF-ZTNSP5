import type { Metadata } from "next";
import { CommandScreen } from "@/components/command/command-screen";
import "./command.css";

export const metadata: Metadata = { title: "Mission command center" };

export default async function MissionCommandPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <CommandScreen missionId={id} />;
}
