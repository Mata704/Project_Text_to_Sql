import hashlib
import json
from collections.abc import Sequence

from text_to_sql.chunking import ChunkingService, DocumentChunk
from text_to_sql.constants import COMPONENT_DOCUMENT_INGESTION_EMBEDDINGS
from text_to_sql.document_ingestion.document_ingestion_model import (
    DocumentIngestionConfig,
    DocumentIngestionResult,
)
from text_to_sql.embeddings import EmbeddingService
from text_to_sql.errors import TextToSQLError
from text_to_sql.usage_metrics import UsageMetricsService
from text_to_sql.vector_store import ChromaDBService


class DocumentIngestionError(TextToSQLError):
    """Raised when documentation cannot be synchronized with the vector store."""


class DocumentIngestionService:
    def __init__(
        self,
        api_key: str,
        config: DocumentIngestionConfig | None = None,
        *,
        chunking_service: ChunkingService | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store_service: ChromaDBService | None = None,
        usage_metrics: UsageMetricsService | None = None,
    ) -> None:
        self.config = config or DocumentIngestionConfig()
        self.chunking_service = chunking_service or ChunkingService()
        self.embedding_service = embedding_service or EmbeddingService(
            api_key=api_key,
            config=self.config.embedding,
            usage_metrics=usage_metrics,
            usage_component=COMPONENT_DOCUMENT_INGESTION_EMBEDDINGS,
        )
        self.vector_store_service = vector_store_service or ChromaDBService(
            config=self.config.vector_store,
        )

    def run(self) -> DocumentIngestionResult:
        documentation_directory = self.config.documentation_directory
        if not documentation_directory.is_dir():
            raise DocumentIngestionError(
                f"Documentation directory does not exist: {documentation_directory}"
            )

        chunks = self.chunking_service.chunk_directory(documentation_directory)
        if not chunks:
            raise DocumentIngestionError(
                f"No Markdown chunks were produced from {documentation_directory}."
            )

        fingerprint = self._fingerprint(chunks)
        if self.vector_store_service.is_corpus_current(fingerprint, len(chunks)):
            return DocumentIngestionResult(
                skipped=True,
                chunk_count=len(chunks),
                embedded_count=0,
                deleted_count=0,
                fingerprint=fingerprint,
            )

        embeddings = self.embedding_service.embed_texts([chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise DocumentIngestionError(
                "The embedding service returned a different number of vectors than chunks."
            )

        self.vector_store_service.upsert_chunks(chunks, embeddings)
        current_ids = {chunk.chunk_id for chunk in chunks}
        stale_ids = self.vector_store_service.get_all_chunk_ids(exclude_ids=current_ids)
        deleted_count = self.vector_store_service.delete_chunks(stale_ids)
        self.vector_store_service.set_corpus_fingerprint(fingerprint)

        return DocumentIngestionResult(
            skipped=False,
            chunk_count=len(chunks),
            embedded_count=len(embeddings),
            deleted_count=deleted_count,
            fingerprint=fingerprint,
        )

    def _fingerprint(self, chunks: Sequence[DocumentChunk]) -> str:
        payload = {
            "embedding_model": self.config.embedding.model,
            "embedding_dimensions": self.config.embedding.dimensions,
            "chunks": [
                {
                    "id": chunk.chunk_id,
                    "content": chunk.content,
                    "metadata": chunk.metadata,
                }
                for chunk in chunks
            ],
        }
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
