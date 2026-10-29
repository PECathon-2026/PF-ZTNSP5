"""Translate the runner's Messages format to/from Azure OpenAI Chat Completions.

No tools execute here. The entire response is validated before it reaches Samurai.
"""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _WireModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")


class _Function(_WireModel):
    name: str = Field(min_length=1, max_length=100)
    arguments: str


class _ToolCall(_WireModel):
    id: str = Field(min_length=1, max_length=200)
    type: Literal["function"]
    function: _Function


class _Message(_WireModel):
    role: Literal["assistant"]
    content: str | None = None
    tool_calls: list[_ToolCall] | None = Field(default=None, max_length=64)
    refusal: str | None = None


class _Choice(_WireModel):
    index: Literal[0]
    message: _Message
    finish_reason: Literal["stop", "tool_calls", "length", "content_filter"]


class _Usage(_WireModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class _Completion(_WireModel):
    choices: list[_Choice] = Field(min_length=1, max_length=1)
    usage: _Usage


def chat_messages(system_prompt: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    for message in messages:
        role = message["role"]
        content = message["content"]
        if isinstance(content, str):
            converted.append({"role": role, "content": content})
            continue
        text = "\n".join(block["text"] for block in content if block["type"] == "text")
        if role == "assistant":
            calls = [{
                "id": block["id"], "type": "function",
                "function": {"name": block["name"], "arguments": json.dumps(block["input"], allow_nan=False)},
            } for block in content if block["type"] == "tool_use"]
            assistant: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                assistant["tool_calls"] = calls
            converted.append(assistant)
        else:
            if text:
                converted.append({"role": "user", "content": text})
            for block in content:
                if block["type"] == "tool_result":
                    converted.append({
                        "role": "tool", "tool_call_id": block["tool_use_id"],
                        "content": block["content"],
                    })
    return converted


def _reject_constant(value: str):
    raise ValueError("Non-finite JSON number")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def messages_envelope(data: Any) -> dict[str, Any]:
    completion = _Completion.model_validate(data)
    choice = completion.choices[0]
    message = choice.message
    calls = message.tool_calls or []
    if bool(calls) != (choice.finish_reason == "tool_calls"):
        raise ValueError("Tool calls and finish reason disagree")
    if message.refusal and calls:
        raise ValueError("Refused completion cannot execute tools")
    blocks: list[dict[str, Any]] = []
    if message.content:
        blocks.append({"type": "text", "text": message.content})
    for call in calls:
        arguments = json.loads(
            call.function.arguments, parse_constant=_reject_constant, object_pairs_hook=_unique_object,
        )
        if not isinstance(arguments, dict):
            raise ValueError("Tool arguments must be a JSON object")
        blocks.append({"type": "tool_use", "id": call.id, "name": call.function.name, "input": arguments})
    if not blocks:
        blocks.append({"type": "text", "text": ""})
    stop = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens", "content_filter": "refusal"}[choice.finish_reason]
    return {
        "content": blocks,
        "stop_reason": "refusal" if message.refusal else stop,
        "usage": {"input_tokens": completion.usage.prompt_tokens, "output_tokens": completion.usage.completion_tokens},
    }


class _ResponseFunction(_WireModel):
    type: Literal["function_call"]
    call_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    arguments: str
    status: Literal["completed"]


class _OutputText(_WireModel):
    type: Literal["output_text"]
    text: str


class _Refusal(_WireModel):
    type: Literal["refusal"]
    refusal: str


class _ResponseMessage(_WireModel):
    type: Literal["message"]
    role: Literal["assistant"]
    status: Literal["completed"]
    content: list[_OutputText | _Refusal]


class _Reasoning(_WireModel):
    type: Literal["reasoning"]
    id: str
    summary: list[dict[str, Any]]
    encrypted_content: str | None = None


class _ResponseUsage(_WireModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class _Response(_WireModel):
    status: Literal["completed"]
    error: None = None
    output: list[_ResponseFunction | _ResponseMessage | _Reasoning] = Field(min_length=1, max_length=64)
    usage: _ResponseUsage


def response_input(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        if message.get("provider_continuation"):
            # Preserve opaque reasoning items and their associated function calls
            # for stateless Responses turns. They never enter the public trace.
            items.extend(message["provider_continuation"])
            continue
        for converted in chat_messages("", [message])[1:]:
            if converted["role"] == "tool":
                items.append({
                    "type": "function_call_output", "call_id": converted["tool_call_id"],
                    "output": converted["content"],
                })
            elif converted["role"] == "assistant":
                if converted["content"]:
                    items.append({"role": "assistant", "content": converted["content"]})
                for call in converted.get("tool_calls", []):
                    items.append({"type": "function_call", "call_id": call["id"], **call["function"]})
            else:
                items.append(converted)
    return items


def response_envelope(data: Any) -> dict[str, Any]:
    response = _Response.model_validate(data)
    blocks = []
    refused = False
    has_tools = False
    for item in response.output:
        if isinstance(item, _ResponseFunction):
            args = json.loads(item.arguments, parse_constant=_reject_constant, object_pairs_hook=_unique_object)
            if not isinstance(args, dict):
                raise ValueError("Tool arguments must be a JSON object")
            blocks.append({"type": "tool_use", "id": item.call_id, "name": item.name, "input": args})
            has_tools = True
        elif isinstance(item, _ResponseMessage):
            for part in item.content:
                if isinstance(part, _Refusal):
                    refused = True
                else:
                    blocks.append({"type": "text", "text": part.text})
    if refused and has_tools:
        raise ValueError("Refused response cannot execute tools")
    return {
        "content": blocks or [{"type": "text", "text": ""}],
        "stop_reason": "refusal" if refused else ("tool_use" if has_tools else "end_turn"),
        "usage": response.usage.model_dump(),
    }
