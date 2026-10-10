from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChunkingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_chunk_chars: int = Field(default=2400, gt=0)
    overlap_chars: int = Field(default=300, ge=0)

    @model_validator(mode="after")
    def validate_overlap(self) -> ChunkingConfig:
        if self.overlap_chars >= self.max_chunk_chars:
            raise ValueError("overlap_chars must be smaller than max_chunk_chars.")
        return self


class DocumentChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    document_title: str = Field(min_length=1)
    section_path: tuple[str, ...] = ()
    chunk_index: int = Field(ge=0)
    total_chunks: int = Field(ge=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    token_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_line_range(self) -> DocumentChunk:
        if self.end_line < self.start_line:
            raise ValueError("end_line must be greater than or equal to start_line.")
        if self.chunk_index >= self.total_chunks:
            raise ValueError("chunk_index must be smaller than total_chunks.")
        return self

    @property
    def metadata(self) -> dict[str, str | int]:
        return {
            "source": self.source,
            "document_title": self.document_title,
            "section": " > ".join(self.section_path),
            "chunk_index": self.chunk_index,
            "total_chunks": self.total_chunks,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "token_count": self.token_count,
        }
