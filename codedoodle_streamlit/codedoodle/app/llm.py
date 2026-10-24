"""Talks to Gemma 4 through the Gemini API using the single GEMINI_API_KEY."""

import json
import os
import re

from .demo import demo_result
from .prompts import build_prompt

DEFAULT_MODEL = "gemma-4-31b-it"


class LLMError(Exception):
    """A problem the user can act on. `status` is the HTTP status to return."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _client():
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise LLMError(
            "GEMINI_API_KEY is not set. Create a free key at https://aistudio.google.com/apikey "
            "and put it in your .env file.",
            status=503,
        )
    # Imported here so DEMO_MODE and the missing-key message work without the SDK loaded.
    from google import genai

    return genai.Client(api_key=key)


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a model reply, tolerating fences and chatter."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("reply JSON is not an object")
    return data


def _strip_code_fence(code: str) -> str:
    code = code.strip("\n")
    m = re.match(r"^```[a-zA-Z+]*\n(.*?)\n?```\s*$", code, re.S)
    return m.group(1) if m else code


def normalize(data: dict, language: str) -> dict:
    """Coerce the model's JSON into the exact shape the frontend expects."""
    trace = []
    for i, raw in enumerate(data.get("trace") or [], start=1):
        if not isinstance(raw, dict):
            continue
        trace.append(
            {
                "step": i,
                "element": str(raw.get("element", "")),
                "explanation": str(raw.get("explanation", "")),
                "state": str(raw.get("state", "")),
            }
        )
    return {
        "diagram_type": str(data.get("diagram_type") or "other"),
        "title": str(data.get("title") or "Untitled sketch"),
        "summary": str(data.get("summary") or ""),
        "language": language,
        "code": _strip_code_fence(str(data.get("code") or "")),
        "sample_stdin": str(data.get("sample_stdin") or ""),
        "trace": trace,
        "uncertainties": [str(u) for u in (data.get("uncertainties") or []) if u],
    }


def analyze_sketch(image_bytes: bytes, mime_type: str, language: str) -> dict:
    if os.getenv("DEMO_MODE") == "1":
        return demo_result(language)

    client = _client()
    from google.genai import types

    model = os.getenv("GEMMA_MODEL", DEFAULT_MODEL)
    image = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    prompt = build_prompt(language)

    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[image, prompt],
                config=types.GenerateContentConfig(temperature=0.2),
            )
        except Exception as exc:  # SDK raises several error types; report them plainly
            raise LLMError(f"The model call failed: {exc}") from exc

        try:
            return normalize(extract_json(response.text or ""), language)
        except (ValueError, json.JSONDecodeError):
            # One retry, with a nudge about the format.
            prompt += "\n\nYour previous reply was not valid JSON. Reply with only the JSON object."

    raise LLMError("The model replied, but not in a format we could read. Try again, or retake the photo with clearer lines.")
