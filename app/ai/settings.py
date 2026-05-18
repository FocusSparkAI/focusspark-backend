import os

from dotenv import load_dotenv


load_dotenv()


class AISettings:
    provider = os.getenv("AI_PROVIDER", "openai")
    model = os.getenv("GITHUB_MODEL", "gpt-4.1")
    temperature = float(os.getenv("AI_TEMPERATURE", 0.7))
    max_tokens = int(os.getenv("AI_MAX_TOKENS", 1000))
    openai_api_key = os.getenv("GITHUB_TOKEN")
    openai_base_url = os.getenv(
        "GITHUB_MODELS_ENDPOINT", "https://models.inference.ai.azure.com"
    )


settings = AISettings()