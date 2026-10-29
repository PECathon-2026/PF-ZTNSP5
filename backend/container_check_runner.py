"""Image-owned runner. Repository code runs only inside the restricted container."""

import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

report_path = Path("/tmp") / f"kage-{uuid4().hex}.json"
command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "--json-report", f"--json-report-file={report_path}", *sys.argv[1:]]
code = subprocess.call(command)
report = None
try:
    if report_path.stat().st_size <= 2_000_000:
        raw = json.loads(report_path.read_text(encoding="utf-8"))
        tests = raw.get("tests", [])
        collectors = raw.get("collectors", [])
        report = {
            "exitcode": raw.get("exitcode"), "summary": raw.get("summary", {}),
            "truncated": len(tests) > 500 or len(collectors) > 500,
            "tests": [{"nodeid": t.get("nodeid"), "outcome": t.get("outcome"),
                       **{stage: t.get(stage, {}).get("outcome") for stage in ("setup", "call", "teardown")}}
                      for t in tests[:500]],
            "collectors": [{"nodeid": c.get("nodeid"), "outcome": c.get("outcome"),
                            "result": [{"nodeid": item.get("nodeid"), "type": item.get("type")}
                                       for item in c.get("result", [])[:500]]} for c in collectors[:500]],
        }
except (OSError, ValueError, TypeError, AttributeError):
    pass
finally:
    report_path.unlink(missing_ok=True)
print("\nKAGE_CHECK_REPORT:" + json.dumps(report), flush=True)
sys.exit(code)
