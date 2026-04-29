"""Gemini text generation client — sync (one-shot) and streaming.

Wraps `google.generativeai.GenerativeModel` so call sites do not import the
SDK directly. Raises `LLMError` on every failure path so the FastAPI error
handler returns a consistent RFC 7807 problem doc.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator

from app.core.config import get_settings
from app.core.errors import LLMError

log = logging.getLogger("api.llm")


def _model():
    settings = get_settings()
    if not settings.GOOGLE_API_KEY:
        raise LLMError("GOOGLE_API_KEY is not set; cannot call Gemini.")
    import google.generativeai as genai

    genai.configure(api_key=settings.GOOGLE_API_KEY)
    return genai.GenerativeModel(settings.GEMINI_MODEL)


def generate_text(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
    retries: int = 2,
) -> str:
    """One-shot generation. Retries on transient errors with linear backoff."""
    last_err: Exception | None = None
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    cfg = {"temperature": temperature, "max_output_tokens": max_output_tokens}
    for attempt in range(1, retries + 2):
        try:
            res = _model().generate_content(full_prompt, generation_config=cfg)
            text = (getattr(res, "text", None) or "").strip()
            if not text:
                raise LLMError("Gemini returned an empty response.")
            return text
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("llm.retry", extra={"attempt": attempt, "error": str(e)[:200]})
            time.sleep(min(2 ** (attempt - 1), 4))
    raise LLMError(f"Gemini generation failed after retries: {last_err}")


def generate_stream(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.2,
    max_output_tokens: int = 1024,
) -> Iterator[str]:
    """Streaming generation. Yields text deltas as they arrive."""
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    cfg = {"temperature": temperature, "max_output_tokens": max_output_tokens}
    try:
        stream = _model().generate_content(full_prompt, generation_config=cfg, stream=True)
        for chunk in stream:
            text = getattr(chunk, "text", None)
            if text:
                yield text
    except Exception as e:  # noqa: BLE001
        raise LLMError(f"Gemini streaming failed: {e}") from e
