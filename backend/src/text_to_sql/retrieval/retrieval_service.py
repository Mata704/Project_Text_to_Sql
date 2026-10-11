from text_to_sql.embeddings import EmbeddingService
from text_to_sql.retrieval.retrieval_model import (
    RetrievalConfig,
    RetrievedChunk,
)
from text_to_sql.vector_store import ChromaDBService


class RetrievalService:
    def __init__(
        self,
        api_key: str,
        config: RetrievalConfig | None = None,
        *,
        embedding_service: EmbeddingService | None = None,
        vector_store_service: ChromaDBService | None = None,
    ) -> None:
        self.config = config or RetrievalConfig()
        self.embedding_service = (
            embedding_service
            if embedding_service is not None
            else EmbeddingService(api_key=api_key, config=self.config.embedding)
        )
        self.vector_store_service = (
            vector_store_service
            if vector_store_service is not None
            else ChromaDBService(config=self.config.vector_store)
        )

    def retrieve(self, query: str) -> list[RetrievedChunk]:
        if not query.strip():
            raise ValueError("The retrieval query cannot be empty.")

        if self.vector_store_service.count() == 0:
            return []

        query_embedding = self.embedding_service.embed_texts([query])[0]
        matches = self.vector_store_service.search(
            query_embedding.vector,
            limit=self.config.top_k,
        )

        retrieved_chunks: list[RetrievedChunk] = []
        for chunk in matches:
            if chunk.distance is None:
                raise ValueError(f"Retrieved chunk {chunk.chunk_id!r} has no vector distance.")
            score = 1.0 - chunk.distance
            if (
                self.config.minimum_similarity_score is not None
                and score < self.config.minimum_similarity_score
            ):
                continue
            retrieved_chunks.append(RetrievedChunk(chunk=chunk, score=score))
        return retrieved_chunks
