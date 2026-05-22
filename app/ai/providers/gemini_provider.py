import time

from .base_provider import BaseProvider
from app.ai.settings import settings


TEMPERATURE = 0.85
TOP_K = 64
TOP_P = 0.95
MAX_OUTPUT_TOKENS = 8192


class GeminiProvider(BaseProvider):
    def __init__(self, model: str | None = None):
        try:
            from google import genai
            from google.genai import types
        except Exception as e:
            raise ImportError(
                "google-genai is required for the Gemini provider. Install with `pip install google-genai`"
            ) from e

        if not settings.gemini_api_key:
            raise ValueError("GOOGLE_API_KEY (or GEMINI_API_KEY) not set for Gemini provider")

        self._types = types
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = model or settings.gemini_model or settings.model
        self.generate_config = types.GenerateContentConfig(
            temperature=TEMPERATURE,
            top_k=TOP_K,
            top_p=TOP_P,
            max_output_tokens=MAX_OUTPUT_TOKENS,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="BLOCK_MEDIUM_AND_ABOVE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_MEDIUM_AND_ABOVE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_MEDIUM_AND_ABOVE",
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_MEDIUM_AND_ABOVE",
                ),
            ],
        )

    def generate(self, prompt: str) -> str:
        last_error = None

        for _ in range(3):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=self.generate_config,
                )
                text = (response.text or "").strip()

                if not text:
                    raise Exception("AI returned empty content")

                return text
            except Exception as e:
                last_error = e
                time.sleep(1)

        if last_error is None:
            raise Exception("AI request failed after retries")

        raise Exception(
            f"AI request failed after retries ({type(last_error).__name__}): {last_error}"
        )
