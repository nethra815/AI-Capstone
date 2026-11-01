"""One place that talks to the LLM: Groq via its OpenAI-compatible endpoint."""
import json
import re

from .config import GROQ_API_KEY, GROQ_BASE_URL, LLM_MODEL


def chat_json(system: str, user: str, max_tokens: int = 900, required_key: str | None = None) -> dict:
    """Send one chat request and return the JSON object in the reply. Raises if none is returned."""
    if not GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY is not set. Export your Groq key before running (see README).")
    from openai import OpenAI
    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    r = client.chat.completions.create(
        model=LLM_MODEL, max_tokens=max_tokens,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    raw = r.choices[0].message.content or ""
    decoder = json.JSONDecoder()
    candidates = []
    for match in re.finditer(r"\{", raw):
        try:
            data, _ = decoder.raw_decode(raw[match.start():])
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        candidates.append(data)
    if required_key:
        for data in candidates:
            if required_key in data:
                return data
    elif candidates:
        return candidates[0]
    if "{" not in raw:
        raise RuntimeError(f"LLM returned no JSON: {raw[:200]!r}")
    if candidates:
        raise RuntimeError(f"LLM JSON is missing required key {required_key!r}: {raw[:200]!r}")
    raise RuntimeError(f"LLM returned malformed JSON: {raw[:200]!r}")
