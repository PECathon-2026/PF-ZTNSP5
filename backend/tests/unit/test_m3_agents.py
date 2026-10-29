import asyncio
import json

import httpx
import pytest

from app.agents.model_adapter import (
    ModelAdapter, ModelAdapterConfig, ModelAdapterError, ModelProtocolError, ModelRateLimitError,
)
from app.agents.samurai import SamuraiConfig, SamuraiRunner
from app.services.repository_service import RepositoryService
from app.services.workspace_service import WorkspaceService
from app.settings import Settings


def envelope(blocks, stop_reason="tool_use"):
    return {"content": blocks, "stop_reason": stop_reason, "usage": {"input_tokens": 10, "output_tokens": 5}}


def call(name, args=None, id="call-1"):
    return {"type": "tool_use", "id": id, "name": name, "input": args or {}}


def adapter_for(handler, **kwargs):
    return ModelAdapter(
        settings=Settings(model_provider="anthropic", anthropic_api_key="test-secret", anthropic_base_url="https://example.test/v1/"),
        transport=httpx.MockTransport(handler), **kwargs,
    )


@pytest.mark.asyncio
async def test_adapter_endpoint_auth_and_tool_roundtrip():
    def handle(request):
        assert str(request.url) == "https://example.test/v1/messages"
        assert request.headers["x-api-key"] == "test-secret"
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["system"] == "system"
        return httpx.Response(200, json=envelope([
            {"type": "text", "text": "Inspect first"}, call("read_file", {"relative_path": "app.py"}),
        ]))

    async with adapter_for(handle) as adapter:
        response = await adapter.chat("system", [{"role": "user", "content": "task"}])
    assert response.tool_calls[0].arguments == {"relative_path": "app.py"}
    assert response.input_tokens == 10
    assert "raw_response" not in response.model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    [], {}, envelope([call("read_file", id="")]),
    envelope([call("read_file"), call("read_file")]),
    envelope([{"type": "tool_use", "id": "x", "name": "read_file", "input": "{}"}]),
    envelope([call("apply_patch")], "max_tokens"),
    envelope([{"type": "text", "text": "done"}]),
    {"content": [{"type": "text", "text": "done"}], "stop_reason": "end_turn", "usage": {"input_tokens": -1, "output_tokens": 0}},
])
async def test_adapter_rejects_malformed_envelopes(payload):
    async with adapter_for(lambda _: httpx.Response(200, json=payload)) as adapter:
        with pytest.raises(ModelProtocolError):
            await adapter.chat("system", [])


@pytest.mark.asyncio
async def test_retries_are_bounded_and_errors_do_not_echo_secrets(caplog):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(429, text="test-secret: private upstream error")

    async with adapter_for(handle, config=ModelAdapterConfig(max_retries=2, retry_base_delay=0.0)) as adapter:
        with pytest.raises(ModelRateLimitError) as error:
            await adapter.chat("system", [])
    assert len(requests) == 3
    assert "test-secret" not in str(error.value) + caplog.text


@pytest.mark.asyncio
async def test_transient_failure_recovers_but_auth_does_not_retry():
    statuses = [503, 200]

    def handle(_):
        return httpx.Response(statuses.pop(0), json=envelope([{"type": "text", "text": "done"}], "end_turn"))

    async with adapter_for(handle, config=ModelAdapterConfig(retry_base_delay=0.0)) as adapter:
        assert (await adapter.chat("system", [])).stop_reason == "end_turn"
    assert not statuses
    statuses[:] = [401, 200]
    async with adapter_for(handle) as adapter:
        with pytest.raises(ModelAdapterError, match="401"):
            await adapter.chat("system", [])
    assert statuses == [200]


@pytest.mark.asyncio
async def test_total_deadline_and_missing_credentials():
    async def slow(_):
        await asyncio.sleep(1)
        return httpx.Response(200)

    async with adapter_for(slow, config=ModelAdapterConfig(total_timeout_seconds=0.01)) as adapter:
        with pytest.raises(ModelAdapterError, match="deadline"):
            await adapter.chat("system", [])
    async with ModelAdapter(settings=Settings(model_provider="anthropic", anthropic_api_key="")) as adapter:
        with pytest.raises(ModelAdapterError, match="ANTHROPIC_API_KEY"):
            await adapter.chat("system", [])


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "test_app.py").write_text("assert True\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET=hidden", encoding="utf-8")
    service = RepositoryService()
    monkeypatch.setattr(service, "_check_docker", lambda: False)
    record = service.connect_repository(str(repo))
    monkeypatch.setattr("app.services.repository_service._repo_service_instance", service)
    workspaces = WorkspaceService(tmp_path / "workspaces")
    return repo, record["repository_id"], workspaces


def scripted_adapter(actions):
    actions = iter(actions)

    def handle(request):
        body = json.loads(request.content)
        action = next(actions)
        blocks = action(body) if callable(action) else action
        return httpx.Response(200, json=envelope(blocks))

    return adapter_for(handle)


def patch_from_last(body, id="patch", **overrides):
    output = json.loads(body["messages"][-1]["content"][-1]["content"])
    return [call("apply_patch", {
        "relative_path": "app.py", "target": "value = 1", "replacement": "value = 2",
        "expected_fingerprint": output["fingerprint"], **overrides,
    }, id=id)]


def happy_actions():
    return [
        [call("read_file", {"relative_path": "app.py"}, "read")],
        patch_from_last,
        [call("read_file", {"relative_path": "app.py"}, "read-back"), call("read_diff", {"relative_path": "app.py"}, "diff")],
        [call("submit_candidate", {"summary": "Ready"}, "submit")],
    ]


@pytest.mark.asyncio
async def test_samurai_vertical_slice_and_frozen_baseline(workspace):
    repo, repo_id, workspaces = workspace
    async with scripted_adapter(happy_actions()) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces).run(repo_id, "Change value to two")
    assert result.status == "CANDIDATE_READY"
    assert result.model_turns == 4 and result.tool_calls == 5
    assert result.input_tokens == 40
    assert (repo / "app.py").read_text() == "value = 1\n"
    ws = workspaces.get_mission_workspace_dir(result.mission_id)
    assert not (ws / ".env").exists()
    candidate = result.candidate
    assert candidate.changed_files == ["app.py"]
    cand_dir = workspaces.get_candidate_dir(result.mission_id, candidate.id)
    assert workspaces._compute_dir_hash(cand_dir)[0] == candidate.content_fingerprint
    assert not workspaces._leases
    # Later edits cannot mutate the frozen snapshot or the original captured diff.
    (ws / "app.py").write_text("later edit\n")
    (repo / "app.py").write_text("external edit\n")
    diff = workspaces.generate_candidate_diff(result.mission_id, repo_id, candidate.id)
    assert "-value = 1" in diff["unified_diff"] and "+value = 2" in diff["unified_diff"]
    assert (cand_dir / "app.py").read_text() == "value = 2\n"


@pytest.mark.asyncio
async def test_duplicate_patch_id_is_not_executed_twice(workspace):
    _, repo_id, workspaces = workspace
    saved = []

    def patch(body):
        saved.extend(patch_from_last(body, target="value =", replacement="value = 2 +"))
        return saved

    actions = happy_actions()
    actions[1:2] = [patch, lambda _: saved]
    async with scripted_adapter(actions) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces).run(repo_id, "Edit value")
    assert result.status == "CANDIDATE_READY"
    assert result.trace[2].status == "REPLAYED"
    assert (workspaces.get_mission_workspace_dir(result.mission_id) / "app.py").read_text() == "value = 2 + 1\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,args", [
    ("run_check", {}), ("shell", {"command": "echo unsafe"}),
    ("read_file", {"relative_path": "../outside.txt"}),
    ("read_file", {"relative_path": ".env"}),
    ("read_file", {"relative_path": "app.py", "line_start": "1"}),
    ("read_file", {"relative_path": "app.py", "extra": True}),
    ("search_text", {"query": "value", "max_results": 51}),
    ("submit_candidate", {"summary": "I verified everything"}),
])
async def test_untrusted_tools_are_rejected_without_writes(workspace, tool, args):
    repo, repo_id, workspaces = workspace
    async with scripted_adapter([[call(tool, args)]]) as adapter:
        runner = SamuraiRunner(adapter, workspace_service=workspaces, config=SamuraiConfig(max_consecutive_errors=1))
        result = await runner.run(repo_id, "Edit value")
    assert result.status == "BLOCKED"
    assert result.trace[0].status == "ERROR"
    assert (repo / "app.py").read_text() == "value = 1\n"
    assert not workspaces._leases


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [
    {"expected_fingerprint": "0" * 64},
    {"relative_path": "test_app.py", "target": "assert True", "replacement": "assert False"},
    {"content": "value = 2"},
    {"target": "", "replacement": "x"},
])
async def test_invalid_patches_do_not_mutate(workspace, overrides):
    _, repo_id, workspaces = workspace
    actions = [happy_actions()[0], lambda body: patch_from_last(body, **overrides)]
    async with scripted_adapter(actions) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces, config=SamuraiConfig(max_consecutive_errors=1)).run(repo_id, "Edit")
    assert result.status == "BLOCKED"
    assert result.trace[-1].status == "ERROR"
    assert (workspaces.get_mission_workspace_dir(result.mission_id) / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("config", [
    SamuraiConfig(max_turns=1), SamuraiConfig(max_tool_calls=1), SamuraiConfig(max_tokens=1),
])
async def test_budgets_stop_execution_and_release_lease(workspace, config):
    _, repo_id, workspaces = workspace
    async with scripted_adapter(happy_actions()) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces, config=config).run(repo_id, "Edit")
    assert result.status == "BUDGET_EXHAUSTED"
    assert not workspaces._leases
    assert (workspaces.get_mission_workspace_dir(result.mission_id) / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_cancellation_and_concurrent_writer(workspace):
    _, repo_id, workspaces = workspace
    entered = asyncio.Event()

    async def slow(_):
        entered.set()
        await asyncio.Event().wait()

    async with adapter_for(slow) as adapter:
        runner = SamuraiRunner(adapter, workspace_service=workspaces)
        first = asyncio.create_task(runner.run(repo_id, "Edit", mission_id="miss-shared"))
        await entered.wait()
        holder = workspaces._leases["miss-shared"]
        second = await runner.run(repo_id, "Edit", mission_id="miss-shared")
        assert second.status == "BLOCKED"
        assert workspaces._leases["miss-shared"] == holder
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
    assert not workspaces._leases
    assert (workspaces.get_mission_workspace_dir("miss-shared") / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_early_handoff_and_uninspected_second_patch(workspace):
    _, repo_id, workspaces = workspace
    actions = happy_actions()
    actions.insert(3, lambda body: patch_from_last(body, id="second-patch", target="value = 2", replacement="value = 3"))
    async with scripted_adapter(actions) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces, config=SamuraiConfig(max_consecutive_errors=1)).run(repo_id, "Edit")
    assert result.status == "BLOCKED" and result.candidate is None
    assert result.trace[-1].status == "ERROR"


def test_workspace_identifiers_and_same_role_lease(workspace):
    _, repo_id, workspaces = workspace
    with pytest.raises(ValueError):
        workspaces.create_disposable_workspace("../escape", repo_id)
    workspaces.acquire_writer_lease("mission", "SAMURAI")
    from app.services.workspace_service import WriterLeaseError
    with pytest.raises(WriterLeaseError):
        workspaces.acquire_writer_lease("mission", "SAMURAI")


@pytest.mark.asyncio
async def test_network_retries_and_invalid_json_are_sanitized(caplog):
    attempts = 0

    def offline(request):
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("test-secret", request=request)

    async with adapter_for(offline, config=ModelAdapterConfig(max_retries=1, retry_base_delay=0.0)) as adapter:
        with pytest.raises(ModelAdapterError) as error:
            await adapter.chat("system", [])
    assert attempts == 2
    assert "test-secret" not in str(error.value) + caplog.text
    async with adapter_for(lambda _: httpx.Response(200, text="test-secret")) as adapter:
        with pytest.raises(ModelProtocolError, match="invalid JSON"):
            await adapter.chat("system", [])


@pytest.mark.asyncio
async def test_gone_gateway_fails_once_with_remediation():
    attempts = 0

    def gone(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(410, text="test-secret")

    async with adapter_for(gone) as adapter:
        with pytest.raises(ModelAdapterError, match="ANTHROPIC_BASE_URL") as error:
            await adapter.chat("system", [])
    assert attempts == 1
    assert "test-secret" not in str(error.value)


@pytest.mark.asyncio
async def test_read_required_before_existing_file_patch(workspace):
    _, repo_id, workspaces = workspace
    actions = [[call("list_files")], patch_from_last]
    async with scripted_adapter(actions) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces, config=SamuraiConfig(max_consecutive_errors=1)).run(repo_id, "Edit")
    assert result.status == "BLOCKED" and result.trace[-1].status == "ERROR"
    assert (workspaces.get_mission_workspace_dir(result.mission_id) / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
async def test_tool_error_feedback_allows_corrected_request(workspace):
    _, repo_id, workspaces = workspace

    def recover(body):
        previous = body["messages"][-1]["content"][0]
        assert previous["is_error"] is True
        assert json.loads(previous["content"])["status"] == "ERROR"
        return happy_actions()[0]

    actions = [[call("shell", {}, "denied")], recover, *happy_actions()[1:]]
    async with scripted_adapter(actions) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces).run(repo_id, "Edit")
    assert result.status == "CANDIDATE_READY"
    assert result.trace[0].status == "ERROR"


@pytest.mark.asyncio
async def test_runner_timeout_and_protocol_watchdog(workspace):
    _, repo_id, workspaces = workspace

    async def slow(_):
        await asyncio.sleep(1)

    async with adapter_for(slow) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces, config=SamuraiConfig(max_seconds=0.01)).run(repo_id, "Edit")
    assert result.status == "BUDGET_EXHAUSTED"
    assert not workspaces._leases
    async with adapter_for(lambda _: httpx.Response(200, json={})) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces).run(repo_id, "Edit")
    assert result.status == "BLOCKED" and result.model_turns == 3
    assert result.tool_calls == 0
    assert not workspaces._leases


def test_workspace_cannot_be_created_inside_original(workspace):
    repo, repo_id, _ = workspace
    workspaces = WorkspaceService(repo / "storage")
    with pytest.raises(ValueError, match="must not overlap"):
        workspaces.create_disposable_workspace("miss-overlap", repo_id)
    assert not (repo / "storage" / "miss-overlap").exists()


@pytest.mark.asyncio
async def test_relative_storage_root_supports_file_exploration(workspace, tmp_path, monkeypatch):
    _, repo_id, _ = workspace
    monkeypatch.chdir(tmp_path)
    from pathlib import Path
    workspaces = WorkspaceService(Path("relative-storage"))
    actions = [[call("list_files", id="list")], *happy_actions()]
    async with scripted_adapter(actions) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces).run(repo_id, "Edit")
    assert result.status == "CANDIDATE_READY"
    assert result.trace[0].status == "SUCCEEDED"


def azure_adapter(handler, **overrides):
    overrides.setdefault("azure_openai_api", "chat_completions")
    return ModelAdapter(
        settings=Settings(
            model_provider="azure_openai", azure_openai_api_key="azure-test-secret",
            azure_openai_base_url="https://example.openai.azure.com/openai/v1",
            azure_openai_deployment="test-deployment", **overrides,
        ),
        transport=httpx.MockTransport(handler),
    )


def azure_envelope(blocks):
    return {
        "choices": [{
            "index": 0, "finish_reason": "tool_calls",
            "message": {
                "role": "assistant", "content": None,
                "tool_calls": [{
                    "id": block["id"], "type": "function",
                    "function": {"name": block["name"], "arguments": json.dumps(block["input"])},
                } for block in blocks],
            },
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


@pytest.mark.asyncio
async def test_azure_vertical_slice_and_tool_result_roundtrip(workspace):
    repo, repo_id, workspaces = workspace
    turns = 0

    def handle(request):
        nonlocal turns
        turns += 1
        assert str(request.url) == "https://example.openai.azure.com/openai/v1/chat/completions"
        assert request.headers["api-key"] == "azure-test-secret"
        assert "x-api-key" not in request.headers
        body = json.loads(request.content)
        assert body["model"] == "test-deployment"
        assert body["max_completion_tokens"] == 4096
        assert "temperature" not in body and "max_tokens" not in body
        assert body["messages"][0]["role"] == "system"
        assert body["tools"][0]["type"] == "function"
        if turns == 2:
            # The model sees both its function call and the matching tool result.
            assistant, output = body["messages"][-2:]
            assert assistant["role"] == "assistant"
            assert output["role"] == "tool" and output["tool_call_id"] == "read"
            assert assistant["tool_calls"][0]["id"] == "read"
            fingerprint = json.loads(output["content"])["fingerprint"]
            blocks = [call("apply_patch", {
                "relative_path": "app.py", "target": "value = 1", "replacement": "value = 2",
                "expected_fingerprint": fingerprint,
            }, "patch")]
        else:
            blocks = happy_actions()[turns - 1]
        if turns == 4:
            assert [item["role"] for item in body["messages"][-3:]] == ["assistant", "tool", "tool"]
            assert [item["tool_call_id"] for item in body["messages"][-2:]] == ["read-back", "diff"]
        return httpx.Response(200, json=azure_envelope(blocks))

    async with azure_adapter(handle) as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces).run(repo_id, "Edit value")
    assert result.status == "CANDIDATE_READY" and result.tool_calls == 5
    assert result.input_tokens == 40 and result.output_tokens == 20
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", ["not-json", "[]", '"text"', '{"a": NaN}', '{"a": 1, "a": 2}'])
async def test_azure_rejects_malformed_tool_arguments(arguments):
    payload = azure_envelope([call("read_file")])
    payload["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = arguments
    async with azure_adapter(lambda _: httpx.Response(200, json=payload)) as adapter:
        with pytest.raises(ModelProtocolError):
            await adapter.chat("system", [])


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason", ["length", "stop", "content_filter", None])
async def test_azure_rejects_incomplete_or_conflicting_tool_responses(finish_reason):
    payload = azure_envelope([call("apply_patch")])
    payload["choices"][0]["finish_reason"] = finish_reason
    async with azure_adapter(lambda _: httpx.Response(200, json=payload)) as adapter:
        with pytest.raises(ModelProtocolError):
            await adapter.chat("system", [])


@pytest.mark.asyncio
async def test_azure_text_only_response_and_empty_deployment():
    payload = {
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "done"}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1},
    }
    async with azure_adapter(lambda _: httpx.Response(200, json=payload)) as adapter:
        result = await adapter.chat("system", [])
    assert result.text == "done" and result.stop_reason == "end_turn" and not result.tool_calls
    async with ModelAdapter(settings=Settings(
        model_provider="azure_openai", azure_openai_api_key="test-secret",
        azure_openai_base_url="https://example.test/openai/v1", azure_openai_deployment="",
    )) as adapter:
        with pytest.raises(ModelAdapterError, match="deployment name"):
            await adapter.chat("system", [])


def test_provider_readiness_and_settings_do_not_serialize_keys():
    settings = Settings(
        model_provider="azure_openai", azure_openai_api_key="azure-test-secret",
        azure_openai_base_url="https://example.test/openai/v1", azure_openai_deployment="deployed",
        anthropic_api_key="anthropic-test-secret",
    )
    assert settings.model_configured
    assert settings.configured_model_name == "deployed"
    assert "test-secret" not in settings.model_dump_json() + repr(settings)
    settings.azure_openai_deployment = ""
    assert not settings.model_configured


@pytest.mark.parametrize("effort", [None, "none", "low"])
def test_azure_reasoning_effort_is_explicit_and_optional(effort):
    from app.agents.tool_contracts import samurai_tools
    from app.agents.openai_protocol import chat_messages
    settings = Settings(
        model_provider="azure_openai", azure_openai_api_key="test-secret",
        azure_openai_base_url="https://example.test/openai/v1", azure_openai_deployment="test-deployment",
        azure_openai_reasoning_effort=effort,
        azure_openai_api="chat_completions",
    )
    adapter = ModelAdapter(settings=settings)
    try:
        body = adapter._build_request_body("system", [], samurai_tools(), ModelAdapterConfig())
        assert body.get("reasoning_effort") == effort
        assert ("reasoning_effort" in body) == (effort is not None)
        assert chat_messages("system", [{"role": "user", "content": "hello"}])[-1]["content"] == "hello"
    finally:
        asyncio.run(adapter.close())


def responses_envelope(blocks):
    return {
        "status": "completed", "error": None,
        "output": [{"type": "reasoning", "id": "rs_test", "summary": [], "encrypted_content": "opaque-test-state"}] + [{
            "type": "function_call", "id": "fc_" + block["id"], "call_id": block["id"],
            "name": block["name"], "arguments": json.dumps(block["input"]), "status": "completed",
        } for block in blocks],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


@pytest.mark.asyncio
async def test_azure_responses_vertical_slice_preserves_continuation(workspace):
    repo, repo_id, workspaces = workspace
    turns = 0

    def handle(request):
        nonlocal turns
        turns += 1
        assert str(request.url).endswith("/openai/v1/responses")
        body = json.loads(request.content)
        assert body["store"] is False
        assert body["include"] == ["reasoning.encrypted_content"]
        assert body["reasoning"] == {"effort": "low"}
        assert body["max_output_tokens"] == 4096
        assert body["tools"][0]["type"] == "function"
        assert "name" in body["tools"][0] and "function" not in body["tools"][0]
        if turns == 2:
            reasoning, function, output = body["input"][-3:]
            assert reasoning["encrypted_content"] == "opaque-test-state"
            assert function["type"] == "function_call" and function["call_id"] == "read"
            assert output["type"] == "function_call_output" and output["call_id"] == "read"
            fingerprint = json.loads(output["output"])["fingerprint"]
            blocks = [call("apply_patch", {
                "relative_path": "app.py", "target": "value = 1", "replacement": "value = 2",
                "expected_fingerprint": fingerprint,
            }, "patch")]
        else:
            blocks = happy_actions()[turns - 1]
        return httpx.Response(200, json=responses_envelope(blocks))

    async with azure_adapter(handle, azure_openai_api="responses", azure_openai_reasoning_effort="low") as adapter:
        result = await SamuraiRunner(adapter, workspace_service=workspaces).run(repo_id, "Edit value")
    assert result.status == "CANDIDATE_READY"
    assert "opaque-test-state" not in result.model_dump_json()
    assert (repo / "app.py").read_text() == "value = 1\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["incomplete", "malformed", "duplicate", "unsupported", "unfinished"])
async def test_responses_reject_partial_or_invalid_tools(fault):
    payload = responses_envelope([call("read_file")])
    if fault == "incomplete":
        payload["status"] = "incomplete"
    elif fault == "malformed":
        payload["output"][1]["arguments"] = "[]"
    elif fault == "duplicate":
        payload["output"].append(payload["output"][1].copy())
    elif fault == "unfinished":
        payload["output"][1]["status"] = "in_progress"
    else:
        payload["output"].append({"type": "web_search_call"})
    async with azure_adapter(lambda _: httpx.Response(200, json=payload), azure_openai_api="responses") as adapter:
        with pytest.raises(ModelProtocolError):
            await adapter.chat("system", [])


@pytest.mark.asyncio
async def test_responses_text_and_private_continuation():
    payload = responses_envelope([])
    payload["output"].append({
        "type": "message", "role": "assistant", "status": "completed",
        "content": [{"type": "output_text", "text": "done"}],
    })
    async with azure_adapter(lambda _: httpx.Response(200, json=payload), azure_openai_api="responses") as adapter:
        result = await adapter.chat("system", [])
    assert result.text == "done" and result.stop_reason == "end_turn"
    assert result.provider_continuation == payload["output"]
    assert "opaque-test-state" not in result.model_dump_json()
