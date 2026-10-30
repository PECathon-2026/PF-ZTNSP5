/** Raw-byte fingerprint for this walkthrough's fixed two-file repository. */
import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { createHash } from "node:crypto";

export async function fingerprintFixture(repo) {
  const names = (await readdir(repo)).sort();
  if (names.join(",") !== "pagination.py,test_pagination.py") throw new Error("Unexpected demo repository manifest");
  const hash = createHash("sha256");
  for (const name of names) {
    const path = Buffer.from(name, "utf8");
    const length = Buffer.alloc(8);
    length.writeBigUInt64BE(BigInt(path.length));
    hash.update(length).update(path).update(createHash("sha256").update(await readFile(join(repo, name))).digest());
  }
  return hash.digest("hex");
}
