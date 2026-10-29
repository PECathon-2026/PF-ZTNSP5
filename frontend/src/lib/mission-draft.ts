export const MAX_CRITERIA = 12;

export function normalizeCriterion(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function addCriterion(criteria: string[], value: string): { criteria: string[]; error: string } {
  const text = normalizeCriterion(value);
  if (!text) return { criteria, error: "Write a criterion before adding it." };
  if (text.length > 300) return { criteria, error: "Keep each criterion under 300 characters." };
  if (criteria.length >= MAX_CRITERIA) return { criteria, error: `You can add up to ${MAX_CRITERIA} criteria.` };
  if (criteria.some((entry) => entry.toLocaleLowerCase() === text.toLocaleLowerCase())) {
    return { criteria, error: "That criterion is already in the list." };
  }
  return { criteria: [...criteria, text], error: "" };
}

export function classifyHealth(response: { ok: boolean }, contentType: string, body: unknown): { state: "unavailable" | "responding"; label: string; detail: string } {
  if (!response.ok || !contentType.toLowerCase().includes("application/json") || !body || typeof body !== "object" || Array.isArray(body)) {
    return { state: "unavailable", label: "API unavailable", detail: "No compatible local API responded at /api/health." };
  }
  return { state: "responding", label: "API responding", detail: "Health endpoint responded; model and execution readiness are still unverified." };
}
