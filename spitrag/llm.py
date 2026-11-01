"""One place that talks to the LLM: Groq via its OpenAI-compatible endpoint."""
import json
import re
import sys
import time

from .config import GROQ_API_KEY, GROQ_BASE_URL, LLM_MODEL, LLM_SEED, LLM_TIMEOUT_S

_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL, timeout=LLM_TIMEOUT_S, max_retries=1)
    return _client


def _retry_after(err) -> float:
    """Seconds the provider asked us to wait ("Please try again in 5.64s"), default 10."""
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(err))
    return (int(m.group(1) or 0) * 60 + float(m.group(2))) if m else 10.0


def _create(max_wait: float, **kwargs):
    """One completion. A rate limit with a short suggested wait is waited out (at most twice)."""
    from openai import RateLimitError
    for attempt in range(3):
        try:
            return _get_client().chat.completions.create(**kwargs)
        except RateLimitError as e:
            wait = _retry_after(e)
            if attempt == 2 or wait > max_wait:
                raise
            print(f"[llm] rate limited, waiting {wait:.1f}s", file=sys.stderr)
            time.sleep(wait + 0.5)


def _parse(raw: str, required_key: str | None):
    decoder = json.JSONDecoder()
    candidates = []
    for match in re.finditer(r"\{", raw):
        try:
            data, _ = decoder.raw_decode(raw[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
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


def chat_json(system: str, user: str, max_tokens: int = 900, required_key: str | None = None,
              temperature: float | None = None, reasoning_effort: str | None = None, seed: int | None = LLM_SEED,
              max_wait: float = 20.0) -> dict:
    """Send one chat request and return the JSON object in the reply. Raises if none is returned.

    temperature=0 and a fixed seed make repeated runs as stable as the provider allows. reasoning_effort ("low",
    "medium", "high") applies to reasoning models such as gpt-oss.
    """
    if not GROQ_API_KEY:
        raise SystemExit("GROQ_API_KEY is not set. Export your Groq key before running (see README).")
    kwargs = {"model": LLM_MODEL, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if seed is not None:
        kwargs["seed"] = seed
    if reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    r = _create(max_wait, max_tokens=max_tokens, **kwargs)
    return _parse(r.choices[0].message.content or "", required_key)
