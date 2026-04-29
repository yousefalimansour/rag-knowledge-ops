from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class SourceIngestIn(BaseModel):
    """Slack/Notion JSON ingestion. The shape of `payload` is validated by the extractor."""

    model_config = ConfigDict(extra="forbid")
    source: Literal["slack", "notion"]
    title: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any]
