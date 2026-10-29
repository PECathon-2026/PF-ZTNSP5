import type { Metadata } from "next";
import { MissionSetup } from "@/components/mission-setup";

export const metadata: Metadata = { title: "New mission" };

export default function SetupPage() { return <MissionSetup />; }
