/** Display-only parsing; the complete request is always retained unchanged. */
export function shortMissionTitle(text: string, max = 100) {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return "Untitled mission";
  if (normalized.length <= max) return normalized;
  const prefix = normalized.slice(0, max - 1);
  const boundary = prefix.lastIndexOf(" ");
  return `${prefix.slice(0, boundary > max / 2 ? boundary : prefix.length)}…`;
}

export function missionBrief(text: string) {
  const parent = /^Follow-up to (miss-[A-Za-z0-9_-]+)\.\s*/i.exec(text);
  let originalRequest = text;
  let clarifications = "";
  let instructions = "";
  if (parent) {
    const marker = /Original request:\s*/i.exec(text);
    if (marker) {
      let content = text.slice(marker.index + marker[0].length);
      const next = /New user instructions:\s*/i.exec(content);
      if (next) {
        instructions = content.slice(next.index + next[0].length).trim();
        content = content.slice(0, next.index);
      }
      const prior = /Prior user clarifications(?:\s*\([^)]*\))?:\s*/i.exec(content);
      if (prior) {
        clarifications = content.slice(prior.index + prior[0].length).trim();
        content = content.slice(0, prior.index);
      }
      originalRequest = content.trim();
    }
  }
  const exchanges = clarifications.split(/(?:^|\n|\s)-\s*Question:\s*/i).filter(s => s.trim()).map(segment => {
    const answer = /\bAnswer:\s*/i.exec(segment);
    return answer ? { question: segment.slice(0, answer.index).trim(), answer: segment.slice(answer.index + answer[0].length).trim() }
      : { question: segment.trim(), answer: "" };
  });
  return { title: shortMissionTitle(originalRequest), originalRequest, instructions, exchanges,
    parentMissionId: parent?.[1] || null, fullText: text };
}
