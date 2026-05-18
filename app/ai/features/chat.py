from app.ai.engine import generate_text
from app.ai.prompts.chat_prompt import build_chat_prompt


def chat_feature(message: str, document_text: str | None = None, document_name: str | None = None):
    prompt = build_chat_prompt(message, document_text=document_text, document_name=document_name)
    return generate_text(prompt)