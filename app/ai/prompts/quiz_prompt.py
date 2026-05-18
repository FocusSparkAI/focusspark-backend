from app.models.quiz_model import QuizDifficulty


def get_question_count(difficulty: QuizDifficulty) -> int:
    """Return the number of questions based on difficulty level."""
    question_counts = {
        QuizDifficulty.BEGINNER: 5,
        QuizDifficulty.INTERMEDIATE: 8,
        QuizDifficulty.ADVANCED: 12,
    }
    return question_counts.get(difficulty, 5)


def build_quiz_prompt(content: str, difficulty: QuizDifficulty):
    question_count = get_question_count(difficulty)
    
    return f"""
Generate {question_count} MCQs in JSON:

[
  {{
    "question": "...",
    "options": ["A","B","C","D"],
    "correct_answer_index": 0
  }}
]

Rules:
- Generate exactly {question_count} questions.
- Return ONLY valid JSON (no markdown, no explanation text).
- "correct_answer_index" must be an integer and zero-based.
- The index must point to one item in "options".
- Match the requested difficulty level exactly: {difficulty.value}.
- Difficulty guide: Beginner = simple recall, Intermediate = concept application, Advanced = deeper reasoning and tricky distractors.
- Beginner: {question_count} questions, straightforward content testing.
- Intermediate: {question_count} questions, requires application of concepts.
- Advanced: {question_count} questions, complex scenarios, subtle differences between options.

Content:
{content}
"""