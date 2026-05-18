def build_chat_prompt(message: str, document_text: str | None = None, document_name: str | None = None):
    prompt = [
        "You are an AI Tutor.",
        "",
        "Explain clearly and simply:",
        "",
    ]

    if document_text:
        if document_name:
            prompt.append(f"Document name: {document_name}")
        prompt.append("Document content:")
        prompt.append(document_text)
        prompt.append("")

    prompt.append("User request:")
    prompt.append(message)
    return "\n".join(prompt)