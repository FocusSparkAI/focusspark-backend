from app.ai.provider import provider


def generate_text(prompt: str) -> str:
    return provider.generate(prompt)