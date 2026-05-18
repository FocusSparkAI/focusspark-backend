from app.ai.engine import generate_text
from app.ai.prompts.flashcard_prompt import build_flashcard_prompt
from app.ai.utils import safe_json_load


def flashcard_feature(content: str):
    prompt = build_flashcard_prompt(content)
    result = generate_text(prompt)
    return safe_json_load(result)