import type { Metadata } from "next";
import { ForgeScreen } from "@/components/forge/forge-screen";
import "../../../tree.css";
import "./forge.css";

export const metadata: Metadata = { title: "Forge workspace" };

export default async function ForgePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ForgeScreen missionId={id} />;
}
