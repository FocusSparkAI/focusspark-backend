from app.ai.provider import get_provider
from app.ai.settings import settings


SUPPORTED_PROVIDERS = ("openai", "gemini")


def _normalize_provider(provider_name: str | None) -> str:
    normalized = (provider_name or settings.provider or "openai").strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        return "openai"
    return normalized


def _provider_order(provider_name: str | None) -> list[str]:
    preferred = _normalize_provider(provider_name)
    return [preferred, *[name for name in SUPPORTED_PROVIDERS if name != preferred]]


def generate_text(
    prompt: str,
    provider_name: str | None = None,
    model_name: str | None = None,
    allow_fallback: bool = True,
) -> str:
    """Generate text using the specified provider.

    If the preferred provider fails, the other configured provider is tried.
    A custom model is applied only to the preferred provider.
    """
    providers = _provider_order(provider_name)
    if not allow_fallback:
        providers = providers[:1]

    last_error: Exception | None = None
    preferred_provider = providers[0]
    for current_provider in providers:
        try:
            provider_model = model_name if current_provider == preferred_provider else None
            return get_provider(current_provider, provider_model).generate(prompt)
        except Exception as exc:
            last_error = exc

    if last_error:
        raise last_error

    raise RuntimeError("No AI providers are configured")
