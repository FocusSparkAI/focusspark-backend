from app.ai.settings import settings

from app.ai.providers.openai_provider import OpenAIProvider
from app.ai.providers.gemini_provider import GeminiProvider


def _build_provider(name: str | None = None, model: str | None = None):
    name = (name or settings.provider or "").lower()
    if name == "openai" or not name:
        return OpenAIProvider(model=model)
    if name == "gemini":
        return GeminiProvider(model=model)
    raise ValueError(f"AI provider '{name}' not supported")


# Default provider instance for compatibility (uses env/defaults)
provider = _build_provider(None, None)


def get_provider(name: str | None = None, model: str | None = None):
    """Return a provider instance for the given provider name and optional model.

    If `model` is None, providers will fall back to their configured defaults.
    """
    return _build_provider(name, model)