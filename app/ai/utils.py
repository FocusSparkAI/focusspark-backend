import json
import re


def safe_json_load(text: str):
    try:
        return json.loads(text)
    except Exception:
        # Common LLM format: fenced JSON (```json ... ```).
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if fence:
            try:
                return json.loads(fence.group(1))
            except Exception:
                pass

        # Fallback: extract the first JSON object/array-looking segment.
        first_obj = text.find("{")
        first_arr = text.find("[")
        starts = [i for i in (first_obj, first_arr) if i != -1]
        if starts:
            start = min(starts)
            for end in range(len(text), start, -1):
                candidate = text[start:end].strip()
                try:
                    return json.loads(candidate)
                except Exception:
                    continue

        return {"error": "Invalid JSON from AI", "raw": text}