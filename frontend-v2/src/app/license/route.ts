import { mitLicense } from "@/lib/license";

export function GET() {
  return new Response(mitLicense, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Content-Disposition": 'attachment; filename="KAGE-AI-LICENSE.txt"',
      "X-Content-Type-Options": "nosniff",
    },
  });
}
