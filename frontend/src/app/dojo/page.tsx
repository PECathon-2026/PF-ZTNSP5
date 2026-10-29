import { redirect } from "next/navigation";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Dojo" };

export default function DojoPage() {
  redirect("/");
  return null;
}
