from pathlib import Path
from typing import Any
from app.services.workspace_service import get_workspace_service, WriterLeaseError
from app.tools.files import list_files, read_file
from app.tools.search import search_text
from app.tools.editor import apply_patch
from app.tools.diff import read_diff
from app.tools.checks import run_check
from app.services.repo_map import repository_map

# Role permission matrix
ALLOWED_ROLE_TOOLS: dict[str, set[str]] = {
    "SHOGUN": {"list_files", "search_text", "read_file", "repo_map", "request_clarification"},
    "SAMURAI": {"list_files", "search_text", "read_file", "repo_map", "apply_patch", "read_diff"},
    "SENTINEL": {"list_files", "read_file", "run_check", "report_finding"},
    "SHADOW_COUNCIL": {"list_files", "read_file", "read_diff", "report_finding"},
}


class ToolGatewayError(Exception):
    """Raised when a tool invocation is denied or invalid."""
    pass


class ToolGateway:
    """
    Validated tool gateway. Enforces permissions, writer lease, and path safety
    outside of model instructions.
    """

    def __init__(self):
        self.workspace_service = get_workspace_service()

    def execute_tool(
        self,
        agent_role: str,
        tool_name: str,
        arguments: dict[str, Any],
        mission_id: str,
        workspace_dir: Path,
        base_dir: Path | None = None,
        lease_holder: str | None = None,
    ) -> dict[str, Any]:
        """
        Validates and executes an approved tool call.
        """
        allowed = ALLOWED_ROLE_TOOLS.get(agent_role.upper())
        if not allowed or tool_name not in allowed:
            raise ToolGatewayError(
                f"Tool '{tool_name}' is not permitted for role '{agent_role}'."
            )

        if tool_name == "repo_map":
            return {"status": "SUCCEEDED", **repository_map(workspace_dir)}
        elif tool_name == "list_files":
            subpath = arguments.get("subpath", "")
            files = list_files(workspace_dir, subpath)
            return {"status": "SUCCEEDED", "files": files, "count": len(files)}

        elif tool_name == "read_file":
            rel_path = arguments.get("relative_path")
            if not rel_path:
                raise ToolGatewayError("Missing required argument: 'relative_path'.")
            line_start = arguments.get("line_start")
            line_end = arguments.get("line_end")
            res = read_file(workspace_dir, rel_path, line_start, line_end)
            return {"status": "SUCCEEDED", **res}

        elif tool_name == "search_text":
            query = arguments.get("query", "")
            regex = bool(arguments.get("regex", False))
            max_res = int(arguments.get("max_results", 50))
            matches = search_text(workspace_dir, query, regex, max_res)
            return {"status": "SUCCEEDED", "matches": matches, "count": len(matches)}

        elif tool_name == "apply_patch":
            # Strictly verify that calling agent holds the writer lease
            current_holder = self.workspace_service._leases.get(mission_id)
            if current_holder != (lease_holder or agent_role):
                raise WriterLeaseError(
                    f"Agent '{agent_role}' cannot write. Active writer lease is held by '{current_holder}'."
                )

            rel_path = arguments.get("relative_path")
            if not rel_path:
                raise ToolGatewayError("Missing required argument: 'relative_path'.")

            target = arguments.get("target")
            replacement = arguments.get("replacement")
            content = arguments.get("content")
            delete = arguments.get("delete", False)

            res = apply_patch(workspace_dir, rel_path, target, replacement, content, delete)
            return {"status": "SUCCEEDED", "patch": res}

        elif tool_name == "read_diff":
            if not base_dir:
                raise ToolGatewayError("Baseline directory required to compute diff.")
            rel_path = arguments.get("relative_path")
            if not rel_path:
                raise ToolGatewayError("Missing required argument: 'relative_path'.")

            diff_str = read_diff(base_dir, workspace_dir, rel_path)
            return {"status": "SUCCEEDED", "relative_path": rel_path, "diff": diff_str}

        elif tool_name == "run_check":
            profile = arguments.get("check_profile", "python_pytest")
            selector = arguments.get("test_selector")
            res = run_check(workspace_dir, profile, selector)
            return res

        elif tool_name == "report_finding":
            return {"status": "SUCCEEDED", "reported": True, "finding": arguments}

        elif tool_name == "request_clarification":
            return {"status": "SUCCEEDED", "requested": True, "question": arguments.get("question")}

        else:
            raise ToolGatewayError(f"Unknown tool: '{tool_name}'.")


_gateway_instance: ToolGateway | None = None


def get_tool_gateway() -> ToolGateway:
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = ToolGateway()
    return _gateway_instance
