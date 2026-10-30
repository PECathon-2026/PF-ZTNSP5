import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fingerprintFixture } from "../scripts/demo-integrity.mjs";

test("live integrity checks distinguish raw line endings and reject extra files", async () => {
  const parent = join(tmpdir(), "opencode");
  await mkdir(parent, { recursive: true });
  const directory = await mkdtemp(join(parent, "kage-integrity-"));
  try {
    await writeFile(join(directory, "test_pagination.py"), "assert True\n");
    await writeFile(join(directory, "pagination.py"), "value = 1\n");
    const lf = await fingerprintFixture(directory);
    await writeFile(join(directory, "pagination.py"), "value = 1\r\n");
    assert.notEqual(await fingerprintFixture(directory), lf);
    await writeFile(join(directory, "extra.py"), "unexpected = True\n");
    await assert.rejects(fingerprintFixture(directory), /Unexpected demo repository manifest/);
  } finally { await rm(directory, { recursive: true, force: true }); }
});
