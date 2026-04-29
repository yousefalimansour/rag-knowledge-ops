from __future__ import annotations

import re
import unicodedata

# Strip C0/C1 control chars except common whitespace (\t \n \r).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_TRAILING_WS_RE = re.compile(r"[ \t]+(\n|$)")
_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """NFKC + control-char strip + whitespace collapse.

    Cheap and stable: same input → same output, so the content_hash computed
    over normalized text is reproducible.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _TRAILING_WS_RE.sub(r"\1", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()
