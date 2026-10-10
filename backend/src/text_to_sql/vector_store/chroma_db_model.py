import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChromaDBConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    collection_name: str = Field(default="train_documentation", min_length=1)
    persist_directory: Path | None = None
    distance_metric: Literal["cosine", "l2", "ip"] = "cosine"
    batch_size: int = Field(default=500, gt=0)

    @field_validator("collection_name")
    @classmethod
    def validate_collection_name(cls, name: str) -> str:
        name = name.strip()
        if not name:
            raise ValueError("The ChromaDB collection name cannot be empty.")
        return name


class StoredChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    metadata: dict[str, str | int | float | bool]
    distance: float | None = None

    @field_validator("distance")
    @classmethod
    def validate_distance(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Distance must be a finite number.")
        return value
