from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from text_to_sql.interaction_logs.interaction_log_service import InteractionLogEntry
from text_to_sql.usage_metrics.usage_metrics_service import UsageMetricsReport


class InteractionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rank: int = Field(ge=1)
    question: str | None = None
    source: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    score: float
    content: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)


class InteractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    session_id: str = Field(serialization_alias="sessionId", min_length=1)
    role: Literal["assistant"] = "assistant"
    question: str | None
    answer: str | None
    evidence: list[InteractionEvidence] = Field(default_factory=list)
    usage_metrics: UsageMetricsReport = Field(serialization_alias="usageMetrics")
    logs: list[InteractionLogEntry] = Field(default_factory=list)
    error: str | None = None
