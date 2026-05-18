from app.ai.engine import generate_text
from app.ai.prompts.quiz_prompt import build_quiz_prompt
from app.ai.utils import safe_json_load
from app.models.quiz_model import QuizDifficulty


def quiz_feature(content: str, difficulty: QuizDifficulty):
    prompt = build_quiz_prompt(content, difficulty)
    result = generate_text(prompt)
    return safe_json_load(result)