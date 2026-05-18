from openai import OpenAI
from app.ai.settings import settings
import time


class AIProvider:

    def __init__(self):
        if settings.provider != "openai":
            raise ValueError("Currently only OpenAI supported")

        if not settings.openai_api_key:
            raise ValueError("GITHUB_TOKEN not set")

        base_url = settings.openai_base_url

        if base_url:
            self.client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=base_url,
            )
        else:
            self.client = OpenAI(api_key=settings.openai_api_key)

    def generate(self, prompt: str) -> str:
        last_error = None

        for _ in range(3):  # retry logic
            try:
                response = self.client.chat.completions.create(
                    model=settings.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=settings.temperature,
                    max_tokens=settings.max_tokens,
                )
                content = response.choices[0].message.content
                if not content:
                    raise Exception("AI returned empty content")
                return content

            except Exception as e:
                last_error = e
                time.sleep(1)

        if last_error is None:
            raise Exception("AI request failed after retries")

        raise Exception(
            f"AI request failed after retries ({type(last_error).__name__}): {last_error}"
        )


provider = AIProvider()