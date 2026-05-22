from .base_provider import BaseProvider
from app.ai.settings import settings
import time


class GeminiProvider(BaseProvider):
    def __init__(self, model: str | None = None):
        try:
            import google.generativeai as genai
        except Exception as e:
            raise ImportError(
                "google.generativeai is required for the Gemini provider. Install with `pip install google-generativeai`"
            ) from e

        self._genai = genai

        if not settings.gemini_api_key:
            raise ValueError("GOOGLE_API_KEY (or GEMINI_API_KEY) not set for Gemini provider")

        # Configure client
        try:
            # newer client uses configure
            if hasattr(self._genai, "configure"):
                self._genai.configure(api_key=settings.gemini_api_key)
        except Exception:
            # ignore configure failures; calls below will surface errors
            pass

        # allow explicit gemini model or fallback to shared model
        self.model = model or settings.gemini_model or settings.model

    def generate(self, prompt: str) -> str:
        last_error = None

        for _ in range(3):
            try:
                # Preferred high-level helper if present
                if hasattr(self._genai, "generate_text"):
                    resp = self._genai.generate_text(model=self.model, prompt=prompt)

                    # Response can be a dict-like or object; try common locations
                    text = None
                    if isinstance(resp, dict):
                        text = resp.get("text") or (
                            resp.get("candidates") and resp["candidates"][0].get("output")
                        )
                    else:
                        text = getattr(resp, "text", None) or getattr(resp, "output", None)

                    if not text:
                        raise Exception("AI returned empty content")

                    return text

                # Fallback to chat-style API surface if available
                if hasattr(self._genai, "chat") and hasattr(self._genai.chat, "completions"):
                    r = self._genai.chat.completions.create(
                        model=self.model, messages=[{"role": "user", "content": prompt}]
                    )

                    # Parse common structures
                    text = None
                    if isinstance(r, dict):
                        candidates = r.get("candidates") or r.get("choices")
                        if candidates and isinstance(candidates, list) and candidates:
                            first = candidates[0]
                            if isinstance(first, dict):
                                text = first.get("content") or first.get("output")
                            else:
                                text = getattr(first, "content", None)
                    else:
                        candidates = getattr(r, "candidates", None) or getattr(r, "choices", None)
                        if candidates and len(candidates) > 0:
                            first = candidates[0]
                            text = getattr(first, "content", None) or getattr(first, "output", None)

                    if not text:
                        raise Exception("AI returned empty content")

                    return text

                raise Exception("No supported google.generativeai method found on client")

            except Exception as e:
                last_error = e
                time.sleep(1)

        if last_error is None:
            raise Exception("AI request failed after retries")

        raise Exception(
            f"AI request failed after retries ({type(last_error).__name__}): {last_error}"
        )
