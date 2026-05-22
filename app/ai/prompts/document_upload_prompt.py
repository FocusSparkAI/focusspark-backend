def build_document_upload_prompt(document_name: str, content: str, max_summary_sentences: int = 5):
    """Builds a prompt to extract metadata and produce a structured JSON summary

    The returned prompt asks the model to return ONLY valid JSON matching the
    schema shown in the example. Keep this function simple and similar in
    structure to other prompt builders in the package.
    """
    return f"""
Extract document metadata and structure, and return ONLY valid JSON.

Schema (example):
{{
  "title": "...",
  "summary": "...",
  "language": "...",
  "keywords": ["..."],
  "sections": [
    {{"title": "...", "summary": "..."}}
  ],
  "length_estimate": "short|medium|long"
}}

Rules:
- Return ONLY valid JSON (no prose, no markdown).
- `summary` should be concise (max {max_summary_sentences} sentences).
- `keywords` should be 5-12 relevant single-word or short-phrase tags.
- `sections` should list main headings or logical chunks with 1-2 sentence summaries.
- If a field cannot be determined, return an empty string or empty list for that field.

Document name:
{document_name}

Document content:
{content}
"""
