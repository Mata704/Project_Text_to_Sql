from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from text_to_sql.embeddings.embedding_model import EmbeddingConfig
from text_to_sql.vector_store.chroma_db_model import ChromaDBConfig

_DEFAULT_DOCUMENTATION_DIRECTORY = Path(__file__).resolve().parents[3] / "documentation"


class DocumentIngestionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    documentation_directory: Path = Field(default=_DEFAULT_DOCUMENTATION_DIRECTORY)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    vector_store: ChromaDBConfig = Field(default_factory=ChromaDBConfig)


class DocumentIngestionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    skipped: bool
    chunk_count: int = Field(ge=0)
    embedded_count: int = Field(ge=0)
    deleted_count: int = Field(ge=0)
    fingerprint: str = Field(min_length=1)
