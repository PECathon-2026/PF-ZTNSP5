/** Read-only follow-up to a saved live run; never retries approval or application. */
import { readFile, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fingerprintFixture } from "./demo-integrity.mjs";

const output = resolve(process.argv[2]);
const original = JSON.parse(await readFile(join(output, "report.json"), "utf8"));
const origin = process.env.KAGE_TEST_BASE_URL || "http://127.0.0.1:3001";
const response = await fetch(`${origin}/api/backend/missions/${original.mission_id}`);
if (!response.ok) throw new Error("Mission could not be read");
const detail = await response.json();
const candidate = detail.candidates.find(c => c.id === original.candidate_id);
const actual = await fingerprintFixture(original.repository);
const result = { checked_at: new Date().toISOString(), mission_id: original.mission_id,
  previous_report: "report.json", status: detail.mission.status,
  explanation: "The initial browser oracle compared raw Windows CRLF against an LF-normalized file-read response. This follow-up compares raw directory fingerprints, without rerunning or modifying the mission.",
  expected: candidate?.content_fingerprint, actual,
  success: detail.mission.status === "APPLIED" && actual === candidate?.content_fingerprint && original.tests_preserved && original.browser_errors.length === 0 };
await writeFile(join(output, "integrity-recheck.json"), JSON.stringify(result, null, 2));
const proof = await fetch(`${origin}/api/backend/missions/${original.mission_id}/proof`);
if (proof.ok) await writeFile(join(output, "proof.json"), JSON.stringify(await proof.json(), null, 2));
console.log(JSON.stringify(result, null, 2));
if (!result.success) process.exitCode = 1;
