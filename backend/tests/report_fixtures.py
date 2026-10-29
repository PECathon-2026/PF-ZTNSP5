"""Controlled report fixtures; never used by application execution."""

def passing_report(*nodeids):
    return {"exitcode": 0, "summary": {"total": len(nodeids), "collected": len(nodeids), "passed": len(nodeids)},
            "truncated": False, "collectors": [], "tests": [
                {"nodeid": node, "outcome": "passed", "setup": "passed", "call": "passed", "teardown": "passed"}
                for node in nodeids]}
