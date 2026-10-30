import type { Evidence } from "./types.ts";

/** Display only measured report fields; an exit code alone never proves criteria. */
export function evidenceDisplay(item: Evidence) {
  const profile = item.metadata.check_profile;
  const title = profile === "python_pytest" ? (item.criterion_id ? "Acceptance check" : "Full test suite")
    : profile === "python_bandit" ? "Security scan"
    : ({ DIFF: "Candidate diff", REVIEW_FINDING: "Code review", MUTATION: "Challenge the fix", BASELINE: "Baseline check" } as Record<string, string>)[item.kind]
      || item.kind.toLowerCase().replaceAll("_", " ");
  const report = item.metadata.report;
  const summary = report && typeof report === "object" && "summary" in report ? report.summary : null;
  const counts: string[] = [];
  if (summary && typeof summary === "object") {
    for (const key of ["passed", "failed", "error", "skipped"]) {
      const value = (summary as Record<string, unknown>)[key];
      if (typeof value === "number" && Number.isInteger(value) && value > 0) counts.push(`${value} ${key}`);
    }
  }
  const result = counts.join(" · ") || (item.exit_code == null ? "Recorded" : `Exit ${item.exit_code}`);
  return { title, result, controlled: item.metadata.controlled_evaluation === true,
    selector: typeof item.metadata.test_selector === "string" ? item.metadata.test_selector : "" };
}
