"""Pluggable LLM client (§8: "OpenAI + Gemini (pluggable) — matches
production pattern of not single-sourcing model risk; enables A/B eval").

Agents call ``complete_json`` with a Pydantic model class and get back a
validated instance, regardless of which provider is configured. Swapping
providers is a config change (LLM_PROVIDER=openai|gemini), not a code
change in any agent.
"""

from __future__ import annotations

import json
import time
from typing import TypeVar

from pydantic import BaseModel
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


_QUOTA_ERROR_MARKERS = ("429", "quota", "resourceexhausted")

# Models that just failed on a quota/rate-limit error get skipped for a
# while rather than retried on every subsequent call in the same process —
# a batch job scoring dozens of postings shouldn't re-discover the same
# exhausted daily quota dozens of times, each with its own retry+backoff.
_COOLDOWN_SECONDS = 300.0
_model_cooldown_until: dict[str, float] = {}


def _is_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _QUOTA_ERROR_MARKERS)


def _extract_json(text: str) -> str:
    """LLMs sometimes wrap JSON in prose or code fences — pull out the
    first balanced {...} block."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise LLMError(f"No JSON object found in LLM output: {text[:200]!r}")
    return text[start : end + 1]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _call_openai(system: str, user: str) -> str:
    from openai import OpenAI

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    try:
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        # Translate every OpenAI SDK failure (rate limits, timeouts,
        # transient 5xxs, auth errors) into the one exception type every
        # call site's graceful-degradation fallback actually catches.
        raise LLMError(f"OpenAI call failed: {exc}") from exc
    return resp.choices[0].message.content or ""


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    # Quota errors are deterministic within the retry window — waiting a
    # few seconds and hitting the same daily cap again just burns time
    # that's better spent falling through to the next model candidate.
    retry=retry_if_exception(lambda exc: not _is_quota_error(exc)),
    reraise=True,
)
def _call_gemini_model(system: str, user: str, model_name: str) -> str:
    import google.generativeai as genai

    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel(
        model_name,
        system_instruction=system,
        generation_config={"response_mime_type": "application/json", "temperature": 0.2},
    )
    try:
        resp = model.generate_content(user)
    except Exception as exc:
        # Same translation as _call_openai — e.g. google.api_core's
        # ResourceExhausted (quota) is a real, common failure mode on
        # Gemini's free tier and must degrade gracefully, not crash the
        # whole graph node processing a batch of postings.
        if _is_quota_error(exc):
            _model_cooldown_until[model_name] = time.monotonic() + _COOLDOWN_SECONDS
        raise LLMError(f"Gemini call ({model_name}) failed: {exc}") from exc
    return resp.text or ""


def _call_gemini(system: str, user: str) -> str:
    """Tries gemini_model, then each of gemini_fallback_models in order.
    Each Gemini model has its own free-tier quota bucket, so a model
    hitting its daily cap doesn't have to take the whole pipeline down —
    the next candidate is usually still fresh. Skips any candidate still
    in its quota cooldown window instead of re-discovering the same
    exhausted quota (with a full retry+backoff) on every call."""
    settings = get_settings()
    now = time.monotonic()
    candidates = settings.gemini_model_candidates
    usable = [m for m in candidates if _model_cooldown_until.get(m, 0) <= now]
    last_error: LLMError | None = None
    for model_name in usable or candidates:  # if everything's cooling down, try anyway
        try:
            return _call_gemini_model(system, user, model_name)
        except LLMError as exc:
            last_error = exc
            continue
    raise last_error or LLMError("No Gemini model candidates configured")


def complete_raw(system: str, user: str, provider: str | None = None) -> str:
    """Dispatches to the configured provider. The API-key check happens
    here, outside the retry-decorated call — a missing key is a config
    error, not a transient failure, so it should fail immediately as a
    catchable LLMError instead of being retried three times and re-wrapped
    as a tenacity.RetryError."""
    settings = get_settings()
    provider = provider or settings.llm_provider
    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is not set")
        return _call_openai(system, user)
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise LLMError("GEMINI_API_KEY is not set")
        return _call_gemini(system, user)
    raise LLMError(f"Unknown LLM provider: {provider!r}")


def complete_json(
    system: str, user: str, schema: type[T], provider: str | None = None
) -> T:
    """Call the configured LLM and validate the JSON response against a
    Pydantic schema. Raises LLMError if the model's output doesn't
    validate after JSON extraction."""
    raw = complete_raw(system, user, provider=provider)
    try:
        payload = json.loads(_extract_json(raw))
    except (json.JSONDecodeError, LLMError) as exc:
        raise LLMError(f"LLM did not return valid JSON: {exc}") from exc
    return schema.model_validate(payload)
