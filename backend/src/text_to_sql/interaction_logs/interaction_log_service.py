from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class InteractionLogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    level: Literal["debug", "info", "warning", "error"]
    component: str = Field(min_length=1)
    event: str = Field(min_length=1)
    message: str = Field(min_length=1)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class InteractionLogService:
    """Stores structured log events for a single user interaction."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or str(uuid4())
        self._entries: list[InteractionLogEntry] = []

    @property
    def entries(self) -> list[InteractionLogEntry]:
        return list(self._entries)

    def record(
        self,
        *,
        level: Literal["debug", "info", "warning", "error"],
        component: str,
        event: str,
        message: str,
        details: dict[str, str | int | float | bool | None] | None = None,
    ) -> InteractionLogEntry:
        entry = InteractionLogEntry(
            timestamp=datetime.now(UTC),
            level=level,
            component=component,
            event=event,
            message=message,
            details=details or {},
        )
        self._entries.append(entry)
        return entry
