def build_flashcard_prompt(content: str, card_count: int | None = None):
    count_rule = (
        f"- Number of cards: Generate exactly {card_count} flashcards."
        if card_count is not None
        else "- Number of cards: Generate as many as needed to cover the topic effectively."
    )

    return f"""
Generate flashcards in JSON:

[
  {{"front": "...", "back": "..."}}
]

Rules:
- Generate flashcards based on the content's key concepts and topic importance.
- Number of cards: {count_rule}
- Front: Keep questions/prompts concise and clear.
- Back: Provide accurate, comprehensive answers.
- Focus on what's important to learn, not difficulty levels.
- Return ONLY valid JSON (no markdown, no explanation text).

Content:
{content}
"""