"""Ephemeral model credentials for the existing single-user demo."""

import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from app.settings import get_settings

_keys: dict[str, tuple[str, str]] = {}


def validate_base_url(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        raise ValueError("Enter a valid model base URL (at most 2048 characters, without whitespace).")
    try:
        url = urlsplit(value)
        host = url.hostname
        port = url.port
    except ValueError:
        raise ValueError("Enter a valid model base URL.") from None
    if (url.scheme not in {"https", "http"} or not host or url.username is not None or url.password is not None
            or url.query or url.fragment or not re.fullmatch(r"[a-zA-Z0-9.:-]+", host)
            or port == 0 or "/../" in url.path or url.path.endswith("/..")):
        raise ValueError("Base URL must be a provider endpoint without embedded credentials, query or fragment.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    local = host.lower() == "localhost" or host.lower().endswith(".localhost") or (address is not None and address.is_loopback)
    if address is not None and not (address.is_global or address.is_loopback):
        raise ValueError("Model base URL may not use a private or link-local IP address.")
    if url.scheme != "https" and not local:
        raise ValueError("Model base URL must use HTTPS (HTTP is allowed only for loopback endpoints).")
    return urlunsplit((url.scheme, url.netloc.lower(), url.path.rstrip("/"), "", ""))


def model_settings_for(key: str, base_url: str | None = None):
    key = key.strip()
    if not key or len(key) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise ValueError("Enter a non-empty API key without whitespace (maximum 4096 characters).")
    settings = get_settings()
    if not settings.configured_model_name:
        raise ValueError("Configure the backend provider and model/deployment first.")
    endpoint = validate_base_url(base_url or settings.model_base_url)
    key_field = "azure_openai_api_key" if settings.model_provider == "azure_openai" else "anthropic_api_key"
    url_field = "azure_openai_base_url" if settings.model_provider == "azure_openai" else "anthropic_base_url"
    return settings.model_copy(update={key_field: key, url_field: endpoint})


async def check_model_connection(key: str, base_url: str | None = None):
    """Probe this provider's actual protocol with one bounded, minimal request."""
    from app.agents.model_adapter import ModelAdapter, ModelAdapterConfig

    settings = model_settings_for(key, base_url)
    async with ModelAdapter(settings=settings, config=ModelAdapterConfig(
            max_tokens=32, max_retries=0, timeout_seconds=10, total_timeout_seconds=12)) as adapter:
        await adapter.chat("Connection check. Reply OK.", [{"role": "user", "content": "OK"}])
    return settings


def set_mission_key(mission_id: str, key: str, base_url: str | None = None) -> None:
    configured = model_settings_for(key, base_url)
    _keys[mission_id] = (configured.model_api_key, configured.model_base_url)


def has_mission_key(mission_id: str) -> bool:
    return mission_id in _keys


def mission_settings(mission_id: str):
    credential = _keys.get(mission_id)
    if not credential:
        raise ValueError("Re-enter this mission's API key and base URL; they are not stored across backend restarts.")
    return model_settings_for(*credential)


def forget_mission_key(mission_id: str) -> None:
    _keys.pop(mission_id, None)


def clear_mission_keys() -> None:
    _keys.clear()


def redact_mission_keys(text: str) -> str:
    for key, _ in tuple(_keys.values()):
        text = text.replace(key, "[REDACTED]")
    return text
