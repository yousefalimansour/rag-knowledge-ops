"""Slack export ingestion.

Canonical input shape (simulated; not the real Slack API):
{
  "channel": "general",
  "messages": [
    {
      "user": "alice",
      "ts": "1717084800.000100" | "2024-05-30T12:00:00Z",
      "text": "...",
      "thread_ts": "1717084800.000100"   // optional; replies share their parent's thread_ts
    }
  ]
}

Threads are reassembled into ordered conversations; each thread becomes its
own section so retrieval can return a coherent slice of dialogue.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any

from app.core.errors import IngestionError
from app.ingestion.normalize import normalize_text
from app.ingestion.types import ExtractedDocument, Section


def extract_slack(*, payload: dict[str, Any], title: str) -> ExtractedDocument:
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise IngestionError("Slack payload missing 'messages' list.")

    channel = payload.get("channel")
    threads: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        thread_key = msg.get("thread_ts") or msg.get("ts") or "loose"
        threads.setdefault(thread_key, []).append(msg)

    sections: list[Section] = []
    for thread_key, msgs in threads.items():
        msgs.sort(key=lambda m: _ts_to_dt(m.get("ts")) or datetime.min.replace(tzinfo=UTC))
        body_lines: list[str] = []
        first_ts: datetime | None = None
        for m in msgs:
            text = (m.get("text") or "").strip()
            if not text:
                continue
            user = (m.get("user") or "user").strip()
            ts = _ts_to_dt(m.get("ts"))
            if ts and first_ts is None:
                first_ts = ts
            stamp = ts.strftime("%Y-%m-%d %H:%M") if ts else "?"
            body_lines.append(f"[{stamp}] {user}: {text}")
        body = normalize_text("\n".join(body_lines))
        if not body:
            continue
        heading = f"#{channel} — thread {thread_key}" if channel else f"thread {thread_key}"
        sections.append(Section(text=body, heading=heading, source_timestamp=first_ts))

    if not sections:
        # Empty doc — caller decides whether to allow zero-chunk docs.
        return ExtractedDocument(
            title=title,
            source_type="slack",
            sections=[],
            metadata={"channel": channel, "reason": "no_messages_or_only_bots"},
        )

    return ExtractedDocument(
        title=title,
        source_type="slack",
        sections=sections,
        metadata={"channel": channel, "thread_count": len(sections)},
    )


def _ts_to_dt(ts: object) -> datetime | None:
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), tz=UTC)
    if isinstance(ts, str):
        # Slack-style "1717084800.000100"
        try:
            return datetime.fromtimestamp(float(ts), tz=UTC)
        except ValueError:
            pass
        # ISO 8601
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None
