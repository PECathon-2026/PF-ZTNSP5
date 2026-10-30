import type { Metadata } from "next";
import { Documentation } from "@/components/documentation";
import "../docs.css";

export const metadata: Metadata = {
  title: "Documentation · KAGE AI",
  description: "Set up KAGE AI, bring your own API key, navigate the engineering guild, inspect evidence, troubleshoot missions, and read the MIT license.",
};

export default function DocsPage() {
  return <Documentation />;
}
