from app.ai.provider import get_provider, provider


def generate_text(prompt: str, provider_name: str | None = None) -> str:
    """Generate text using the specified provider.

    If `provider_name` is None, the module-level default `provider` is used.
    The model is determined by the provider instance (thread or settings).
    """
    if provider_name:
        p = get_provider(provider_name)
    else:
        p = provider

    return p.generate(prompt)