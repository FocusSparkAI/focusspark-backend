from app.ai.engine import generate_text
from app.ai.prompts.chat_prompt import build_chat_prompt
from app.ai.prompts.document_upload_prompt import build_document_upload_prompt


def chat_feature(message: str, document_text: str | None = None, document_name: str | None = None,
                 provider_name: str | None = None, model_name: str | None = None):
    # If a document is provided, first extract a structured summary/metadata
    # using the document upload prompt, then include that in the chat prompt.
    if document_text:
        doc_prompt = build_document_upload_prompt(document_name or "document", document_text)
        # Expecting JSON or structured text from the model; include raw result in chat prompt
        doc_summary = generate_text(doc_prompt, provider_name=provider_name, model_name=model_name)
        prompt = build_chat_prompt(message, document_text=doc_summary, document_name=document_name)
        return generate_text(prompt, provider_name=provider_name, model_name=model_name)

    prompt = build_chat_prompt(message, document_text=document_text, document_name=document_name)
    return generate_text(prompt, provider_name=provider_name, model_name=model_name)
