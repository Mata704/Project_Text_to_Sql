import math

from pydantic import BaseModel, ConfigDict, Field, field_validator

from text_to_sql.embeddings.embedding_model import EmbeddingConfig
from text_to_sql.retrieval.constants import (
    DEFAULT_MINIMUM_SIMILARITY_SCORE,
    DEFAULT_RETRIEVAL_TOP_K,
)
from text_to_sql.vector_store.chroma_db_model import ChromaDBConfig, StoredChunk


class RetrievalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: ChromaDBConfig = Field(default_factory=ChromaDBConfig)
    top_k: int = Field(default=DEFAULT_RETRIEVAL_TOP_K, gt=0)
    minimum_similarity_score: float | None = Field(default=DEFAULT_MINIMUM_SIMILARITY_SCORE)

    @field_validator("minimum_similarity_score")
    @classmethod
    def validate_similarity_score(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("The minimum similarity score must be finite.")
        return value


class RetrievedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk: StoredChunk
    score: float

    @field_validator("score")
    @classmethod
    def validate_score(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("The retrieval score must be finite.")
        return value
