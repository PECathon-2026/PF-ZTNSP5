"""Unified adapter for Anthropic Messages and Azure OpenAI Responses/Chat Completions.

Sends chat-completion requests through the gateway at ``ANTHROPIC_BASE_URL``
using Claude tool_use format.  Includes automatic retry with exponential
back-off for transient errors (429 / 5xx) and structured token-usage tracking.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.settings import Settings, get_settings
from app.agents.openai_protocol import chat_messages, messages_envelope, response_envelope, response_input

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ModelAdapterError(Exception):
    """Base exception for model-adapter failures."""


class ModelRateLimitError(ModelAdapterError):
    """The upstream API returned HTTP 429 — rate-limited."""


class ModelOverloadedError(ModelAdapterError):
    """The upstream API returned HTTP 529 or an ``overloaded_error``."""


class ModelBudgetExhaustedError(ModelAdapterError):
    """Token or turn budget has been exceeded."""


class ModelProtocolError(ModelAdapterError):
    """The gateway returned an invalid or incomplete tool-call envelope."""


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

# HTTP status codes that trigger automatic retry.
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504, 529})


class ModelAdapterConfig(BaseModel):
    """Tuning knobs for a single model-adapter call."""

    model_config = ConfigDict(strict=True, extra="forbid")
    max_tokens: int = Field(default=4096, ge=1, le=16384)
    temperature: float = Field(default=0.0, ge=0, le=1)
    max_retries: int = Field(default=3, ge=0, le=5)
    retry_base_delay: float = Field(default=1.0, ge=0, le=30)
    timeout_seconds: float = Field(default=120.0, gt=0, le=300)
    total_timeout_seconds: float = Field(default=180.0, gt=0, le=600)


class ToolDefinition(BaseModel):
    """A tool the model is allowed to call (JSON-Schema based)."""

    name: str
    description: str
    input_schema: dict[str, Any]


class ToolUseRequest(BaseModel):
    """Represents a single tool-use block returned by the model."""

    model_config = ConfigDict(strict=True, extra="forbid")
    tool_use_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any]


class ModelResponse(BaseModel):
    """Parsed response from the Anthropic-compatible Messages API."""

    text: str | None = None
    tool_calls: list[ToolUseRequest] = Field(default_factory=list)
    stop_reason: str  # "end_turn", "tool_use", "max_tokens"
    input_tokens: int = 0
    output_tokens: int = 0
    raw_response: dict[str, Any] | None = Field(default=None, exclude=True)
    provider_continuation: list[dict[str, Any]] = Field(default_factory=list, exclude=True, repr=False)


class _TextBlock(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    type: Literal["text"]
    text: str


class _ToolBlock(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    type: Literal["tool_use"]
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=100)
    input: dict[str, Any]


class _Usage(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


class _Envelope(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    content: list[_TextBlock | _ToolBlock] = Field(min_length=1, max_length=64)
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "stop_sequence", "refusal", "pause_turn"]
    usage: _Usage


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class ModelAdapter:
    """Async gateway client exposing a common Messages-style tool interface.

    Parameters
    ----------
    config:
        Default configuration applied to every ``chat()`` call unless the
        caller supplies a per-call ``config_override``.
    """

    def __init__(
        self, config: ModelAdapterConfig | None = None, *,
        settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        settings = settings or get_settings()
        self._provider = settings.model_provider
        self._api_key: str = settings.model_api_key
        self._model: str = settings.configured_model_name
        self._base_url = settings.model_base_url
        self._reasoning_effort = settings.azure_openai_reasoning_effort
        self._responses_api = self._provider == "azure_openai" and settings.azure_openai_api == "responses"
        self._config = config or ModelAdapterConfig()

        self._client = httpx.AsyncClient(
            base_url=self._base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(self._config.timeout_seconds),
            transport=transport,
            follow_redirects=False,
        )

    # -- public API --------------------------------------------------------

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
        config_override: ModelAdapterConfig | None = None,
    ) -> ModelResponse:
        """Send a chat-completion request and return a parsed ``ModelResponse``.

        Parameters
        ----------
        system_prompt:
            Inserted as the ``system`` field of the request body.
        messages:
            Anthropic-convention message list.  For tool results use::

                {"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": "...", "content": "..."}
                ]}
        tools:
            Optional list of tools the model may invoke.
        config_override:
            Per-call overrides for ``ModelAdapterConfig`` fields.

        Returns
        -------
        ModelResponse
            Parsed text, tool calls, stop reason, and token usage.

        Raises
        ------
        ModelRateLimitError
            After exhausting retries on HTTP 429.
        ModelOverloadedError
            After exhausting retries on HTTP 529 / ``overloaded_error``.
        ModelAdapterError
            On non-retryable HTTP errors or network failures.
        """
        cfg = config_override or self._config
        if not self._api_key or self._api_key == "your_key_here":
            key_setting = "AZURE_OPENAI_API_KEY" if self._provider == "azure_openai" else "ANTHROPIC_API_KEY"
            raise ModelAdapterError(f"Configure {key_setting} on the backend before running Samurai.")
        if not self._model or not self._base_url:
            raise ModelAdapterError("Configure the model endpoint and deployment name before running Samurai.")
        try:
            async with asyncio.timeout(cfg.total_timeout_seconds):
                return await self._chat_with_retries(system_prompt, messages, tools, cfg)
        except TimeoutError:
            raise ModelAdapterError("Model request exceeded its total retry deadline.") from None

    async def _chat_with_retries(self, system_prompt, messages, tools, cfg) -> ModelResponse:
        body = self._build_request_body(system_prompt, messages, tools, cfg)
        headers = {"api-key": self._api_key} if self._provider == "azure_openai" else {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        last_exc: Exception | None = None
        for attempt in range(cfg.max_retries + 1):
            try:
                response = await self._client.post(
                    "responses" if self._responses_api else ("chat/completions" if self._provider == "azure_openai" else "messages"),
                    json=body,
                    headers=headers,
                    timeout=httpx.Timeout(cfg.timeout_seconds),
                )

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    delay = self._backoff_delay(attempt, cfg.retry_base_delay)
                    logger.warning(
                        "Retryable HTTP %s on attempt %d/%d — backing off %.2fs",
                        response.status_code,
                        attempt + 1,
                        cfg.max_retries + 1,
                        delay,
                    )
                    last_exc = self._status_to_exception(response.status_code)
                    if attempt < cfg.max_retries:
                        await asyncio.sleep(delay)
                        continue
                    raise last_exc

                if response.status_code != 200:
                    if response.status_code == 410:
                        base_setting = "AZURE_OPENAI_BASE_URL" if self._provider == "azure_openai" else "ANTHROPIC_BASE_URL"
                        raise ModelAdapterError(
                            "Model gateway returned HTTP 410 Gone. Confirm a supported "
                            f"{base_setting} and model deployment with the gateway provider."
                        )
                    raise ModelAdapterError(
                        f"Model API error (HTTP {response.status_code}). Check backend model configuration."
                    )

                if len(response.content) > 2_000_000:
                    raise ModelProtocolError("Model response exceeds the size limit.")
                try:
                    data = response.json()
                except ValueError:
                    raise ModelProtocolError("Model returned invalid JSON.") from None
                parsed = self._parse_response(data)
                logger.debug(
                    "Model response: stop=%s input_tokens=%d output_tokens=%d",
                    parsed.stop_reason,
                    parsed.input_tokens,
                    parsed.output_tokens,
                )
                return parsed

            except httpx.HTTPError as exc:
                delay = self._backoff_delay(attempt, cfg.retry_base_delay)
                logger.warning(
                    "Network error on attempt %d/%d (%s) — backing off %.2fs",
                    attempt + 1,
                    cfg.max_retries + 1,
                    type(exc).__name__,
                    delay,
                )
                last_exc = ModelAdapterError("Model gateway network request failed.")
                if attempt < cfg.max_retries:
                    await asyncio.sleep(delay)
                    continue
                raise last_exc from None

        # Should never be reached, but satisfy the type-checker.
        raise ModelAdapterError("Exhausted retries")  # pragma: no cover

    async def close(self) -> None:
        """Close the underlying ``httpx.AsyncClient``."""
        await self._client.aclose()

    async def __aenter__(self) -> ModelAdapter:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    # -- internals ---------------------------------------------------------

    def _build_request_body(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None,
        config: ModelAdapterConfig,
    ) -> dict[str, Any]:
        """Build the selected provider's request body from the common tool interface."""
        if self._responses_api:
            body: dict[str, Any] = {
                "model": self._model, "instructions": system_prompt,
                "input": response_input(messages), "max_output_tokens": config.max_tokens,
                "store": False, "include": ["reasoning.encrypted_content"],
            }
            if self._reasoning_effort is not None:
                body["reasoning"] = {"effort": self._reasoning_effort}
            if tools:
                body["tools"] = [{
                    "type": "function", "name": tool.name, "description": tool.description,
                    "parameters": tool.input_schema, "strict": False,
                } for tool in tools]
                body["tool_choice"] = "auto"
                body["parallel_tool_calls"] = False
            return body
        if self._provider == "azure_openai":
            body: dict[str, Any] = {
                "model": self._model,
                "messages": chat_messages(system_prompt, messages),
                "max_completion_tokens": config.max_tokens,
            }
            # Sampling controls are omitted for Azure reasoning-model compatibility.
            if self._reasoning_effort is not None:
                body["reasoning_effort"] = self._reasoning_effort
            if tools:
                body["tools"] = [{
                    "type": "function",
                    "function": {"name": tool.name, "description": tool.description, "parameters": tool.input_schema},
                } for tool in tools]
                body["tool_choice"] = "auto"
                body["parallel_tool_calls"] = False
            return body
        body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": system_prompt,
            "messages": messages,
        }
        if tools:
            body["tools"] = [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in tools
            ]
        return body

    def _parse_response(self, response_data: dict[str, Any]) -> ModelResponse:
        """Parse an Anthropic Messages API JSON response into ``ModelResponse``.

        Handles ``text`` and ``tool_use`` content blocks, plus the ``usage``
        envelope.
        """
        try:
            if self._responses_api:
                normalized = response_envelope(response_data)
            else:
                normalized = messages_envelope(response_data) if self._provider == "azure_openai" else response_data
            envelope = _Envelope.model_validate(normalized)
        except (ValidationError, ValueError):
            raise ModelProtocolError("Model response does not match the tool-calling API schema.") from None
        text_parts: list[str] = []
        tool_calls: list[ToolUseRequest] = []

        for block in envelope.content:
            if isinstance(block, _TextBlock):
                text_parts.append(block.text)
            else:
                tool_calls.append(
                    ToolUseRequest(
                        tool_use_id=block.id,
                        name=block.name,
                        arguments=block.input,
                    )
                )

        if len({call.tool_use_id for call in tool_calls}) != len(tool_calls):
            raise ModelProtocolError("Duplicate tool-use IDs in a model response.")
        if bool(tool_calls) != (envelope.stop_reason == "tool_use"):
            raise ModelProtocolError("Tool calls and stop reason disagree; no tools were executed.")

        return ModelResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            stop_reason=envelope.stop_reason,
            input_tokens=envelope.usage.input_tokens,
            output_tokens=envelope.usage.output_tokens,
            raw_response=response_data,
            provider_continuation=response_data["output"] if self._responses_api else [],
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _backoff_delay(attempt: int, base_delay: float) -> float:
        """Exponential back-off with full jitter."""
        ceiling = min(30.0, base_delay * (2 ** attempt))
        return random.uniform(0, ceiling)  # noqa: S311

    @staticmethod
    def _status_to_exception(status_code: int) -> ModelAdapterError:
        """Map an HTTP status code to the appropriate error subclass."""
        if status_code == 429:
            return ModelRateLimitError("Model gateway rate limited (HTTP 429).")
        if status_code == 529:
            return ModelOverloadedError("Model gateway overloaded (HTTP 529).")
        return ModelAdapterError(f"Model gateway server error (HTTP {status_code}).")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_adapter_instance: ModelAdapter | None = None


def get_model_adapter() -> ModelAdapter:
    """Retrieve or create the singleton ``ModelAdapter``."""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = ModelAdapter()
    return _adapter_instance
