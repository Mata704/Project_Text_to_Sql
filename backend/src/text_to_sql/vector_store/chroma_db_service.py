import math
from collections.abc import Sequence
from pathlib import Path

import chromadb
from chromadb.errors import ChromaError

from text_to_sql.chunking.chunking_model import DocumentChunk
from text_to_sql.embeddings.embedding_model import TextEmbedding
from text_to_sql.errors import VectorStoreError
from text_to_sql.vector_store.chroma_db_model import ChromaDBConfig, StoredChunk

_DEFAULT_PERSIST_DIRECTORY = Path(__file__).resolve().parents[3] / "data" / "chroma"


class ChromaDBService:
    def __init__(self, config: ChromaDBConfig | None = None) -> None:
        self.config = config or ChromaDBConfig()
        self.persist_directory = (
            (self.config.persist_directory or _DEFAULT_PERSIST_DIRECTORY).expanduser().resolve()
        )
        try:
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(self.persist_directory))
            self.collection = self.client.get_or_create_collection(
                name=self.config.collection_name,
                metadata={
                    "hnsw:space": self.config.distance_metric,
                    "distance_metric": self.config.distance_metric,
                },
                embedding_function=None,
            )
        except (OSError, ChromaError, ValueError) as error:
            raise VectorStoreError(f"Could not open the ChromaDB collection: {error}") from error

        collection_metadata = self.collection.metadata or {}
        stored_metric = collection_metadata.get(
            "distance_metric",
            collection_metadata.get("hnsw:space"),
        )
        if stored_metric != self.config.distance_metric:
            raise VectorStoreError(
                f"Collection '{self.config.collection_name}' uses distance metric "
                f"{stored_metric!r}, not {self.config.distance_metric!r}."
            )

    def upsert_chunks(
        self,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[TextEmbedding],
    ) -> int:
        if len(chunks) != len(embeddings):
            raise ValueError("Each document chunk must have exactly one embedding.")
        if not chunks:
            return 0

        ids = [chunk.chunk_id for chunk in chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("Chunk IDs must be unique within an upsert operation.")

        embedding_models = {embedding.model for embedding in embeddings}
        if len(embedding_models) != 1:
            raise ValueError("All embeddings in one upsert operation must use the same model.")

        dimensions = {len(embedding.vector) for embedding in embeddings}
        if len(dimensions) != 1:
            raise ValueError("All embeddings in one upsert operation must have the same dimension.")

        for index, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True)):
            if chunk.content.strip() != embedding.text.strip():
                raise ValueError(f"Chunk and embedding text do not match at index {index}.")

        embedding_model = next(iter(embedding_models))
        try:
            self._validate_collection_embedding(embedding_model, next(iter(dimensions)))
            for batch_start in range(0, len(chunks), self.config.batch_size):
                batch_chunks = chunks[batch_start : batch_start + self.config.batch_size]
                batch_embeddings = embeddings[batch_start : batch_start + self.config.batch_size]
                self.collection.upsert(
                    ids=[chunk.chunk_id for chunk in batch_chunks],
                    documents=[chunk.content for chunk in batch_chunks],
                    embeddings=[embedding.vector for embedding in batch_embeddings],
                    metadatas=[chunk.metadata for chunk in batch_chunks],
                )
        except (ChromaError, ValueError) as error:
            raise VectorStoreError(f"Could not write chunks to ChromaDB: {error}") from error
        return len(chunks)

    def get_chunks(self, chunk_ids: Sequence[str]) -> list[StoredChunk]:
        if not chunk_ids:
            return []
        if any(not chunk_id.strip() for chunk_id in chunk_ids):
            raise ValueError("Chunk IDs must not be empty.")

        try:
            result = self.collection.get(
                ids=list(chunk_ids),
                include=["documents", "metadatas"],
            )
        except (ChromaError, ValueError) as error:
            raise VectorStoreError(f"Could not read chunks from ChromaDB: {error}") from error

        documents_by_id = {
            chunk_id: (document, metadata)
            for chunk_id, document, metadata in zip(
                result["ids"],
                result["documents"] or [],
                result["metadatas"] or [],
                strict=True,
            )
            if document is not None and metadata is not None
        }
        return [
            StoredChunk(
                chunk_id=chunk_id,
                content=documents_by_id[chunk_id][0],
                metadata=documents_by_id[chunk_id][1],
            )
            for chunk_id in chunk_ids
            if chunk_id in documents_by_id
        ]

    def search(
        self,
        query_embedding: Sequence[float],
        limit: int = 5,
    ) -> list[StoredChunk]:
        if not query_embedding:
            raise ValueError("The query embedding cannot be empty.")
        if not all(math.isfinite(value) for value in query_embedding):
            raise ValueError("The query embedding must contain only finite values.")
        if limit < 1:
            raise ValueError("The search limit must be at least 1.")
        collection_count = self.count()
        if collection_count == 0:
            return []

        try:
            results = self.collection.query(
                query_embeddings=[list(query_embedding)],
                n_results=min(limit, collection_count),
                include=["documents", "metadatas", "distances"],
            )
        except (ChromaError, ValueError) as error:
            raise VectorStoreError(f"Could not search ChromaDB: {error}") from error

        ids = results["ids"][0]
        documents = results["documents"][0] or []
        metadatas = results["metadatas"][0] or []
        distances = results["distances"][0] or []
        if not (len(ids) == len(documents) == len(metadatas) == len(distances)):
            raise VectorStoreError("ChromaDB returned incomplete search results.")

        try:
            return [
                StoredChunk(
                    chunk_id=chunk_id,
                    content=document,
                    metadata=metadata,
                    distance=distance,
                )
                for chunk_id, document, metadata, distance in zip(
                    ids,
                    documents,
                    metadatas,
                    distances,
                    strict=True,
                )
                if document is not None and metadata is not None and distance is not None
            ]
        except (TypeError, ValueError) as error:
            raise VectorStoreError(f"ChromaDB returned invalid search results: {error}") from error

    def count(self) -> int:
        try:
            return self.collection.count()
        except ChromaError as error:
            raise VectorStoreError(f"Could not count ChromaDB records: {error}") from error

    def _validate_collection_embedding(self, model: str, dimensions: int) -> None:
        collection_metadata = self.collection.metadata or {}
        stored_model = collection_metadata.get("embedding_model")
        stored_dimensions = collection_metadata.get("embedding_dimensions")
        if stored_model is not None and stored_model != model:
            raise VectorStoreError(
                f"Collection '{self.config.collection_name}' uses embedding model "
                f"{stored_model!r}, not {model!r}."
            )
        if stored_dimensions is not None and stored_dimensions != dimensions:
            raise VectorStoreError(
                f"Collection '{self.config.collection_name}' uses {stored_dimensions} "
                f"embedding dimensions, not {dimensions}."
            )
        if stored_model is None or stored_dimensions is None:
            metadata = {
                key: value for key, value in collection_metadata.items() if key != "hnsw:space"
            }
            self.collection.modify(
                metadata={
                    **metadata,
                    "embedding_model": model,
                    "embedding_dimensions": dimensions,
                    "distance_metric": self.config.distance_metric,
                }
            )
