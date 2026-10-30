from app.settings import get_settings


def redact_secrets(text: str) -> str:
    """Remove configured backend credentials before persistence or model-visible output."""
    settings = get_settings()
    for secret in (settings.anthropic_api_key, settings.azure_openai_api_key):
        if secret and secret != "your_key_here":
            text = text.replace(secret, "[REDACTED]")
    from app.services.mission_credentials import redact_mission_keys
    return redact_mission_keys(text)
