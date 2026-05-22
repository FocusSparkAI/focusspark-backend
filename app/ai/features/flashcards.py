from app.ai.engine import generate_text
from app.ai.prompts.flashcard_prompt import build_flashcard_prompt
from app.ai.utils import safe_json_load


def flashcard_feature(content: str, card_count: int | None = None):
    prompt = build_flashcard_prompt(content, card_count)
    result = generate_text(prompt)
    return safe_json_load(result)