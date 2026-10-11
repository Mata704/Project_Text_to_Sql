from unittest.mock import Mock

import pytest

from text_to_sql.embeddings import TextEmbedding
from text_to_sql.retrieval import RetrievalConfig, RetrievalService
from text_to_sql.vector_store import StoredChunk


def _stored_chunk(chunk_id: str, distance: float | None) -> StoredChunk:
    return StoredChunk(
        chunk_id=chunk_id,
        content=f"Conteúdo de {chunk_id}",
        metadata={"source": "tables/viagens.md"},
        distance=distance,
    )


def _service(
    matches: list[StoredChunk],
    *,
    config: RetrievalConfig | None = None,
) -> tuple[RetrievalService, Mock, Mock]:
    embedder = Mock()
    embedder.embed_texts.return_value = [
        TextEmbedding(
            text="Qual a origem da viagem?",
            vector=[0.8, 0.2],
            model="text-embedding-3-small",
            index=0,
        )
    ]
    vector_store = Mock()
    vector_store.count.return_value = 3
    vector_store.search.return_value = matches
    service = RetrievalService(
        api_key="test-key",
        config=config,
        embedding_service=embedder,
        vector_store_service=vector_store,
    )
    return service, embedder, vector_store


def test_retrieval_embeds_query_and_returns_ranked_chunks_with_similarity_scores() -> None:
    service, embedder, vector_store = _service(
        [
            _stored_chunk("chunk-1", 0.08),
            _stored_chunk("chunk-2", 0.4),
        ],
        config=RetrievalConfig(top_k=2, minimum_similarity_score=None),
    )

    results = service.retrieve("Qual a origem da viagem?")

    assert [result.chunk.chunk_id for result in results] == ["chunk-1", "chunk-2"]
    assert [result.score for result in results] == pytest.approx([0.92, 0.6])
    embedder.embed_texts.assert_called_once_with(["Qual a origem da viagem?"])
    vector_store.search.assert_called_once_with([0.8, 0.2], limit=2)


def test_retrieval_filters_matches_below_minimum_score() -> None:
    service, _, _ = _service(
        [
            _stored_chunk("relevant", 0.2),
            _stored_chunk("weak-match", 0.9),
        ],
        config=RetrievalConfig(minimum_similarity_score=0.15),
    )

    results = service.retrieve("Qual a origem da viagem?")

    assert [result.chunk.chunk_id for result in results] == ["relevant"]
    assert results[0].score == pytest.approx(0.8)


def test_retrieval_rejects_matches_without_distance() -> None:
    service, _, _ = _service([_stored_chunk("missing-distance", None)])

    with pytest.raises(ValueError, match="has no vector distance"):
        service.retrieve("Qual a origem da viagem?")


def test_retrieval_returns_no_results_without_embedding_when_store_is_empty() -> None:
    service, embedder, vector_store = _service([])
    vector_store.count.return_value = 0

    assert service.retrieve("Qual a origem da viagem?") == []

    embedder.embed_texts.assert_not_called()
    vector_store.search.assert_not_called()


def test_retrieval_rejects_empty_query_before_accessing_services() -> None:
    service, embedder, vector_store = _service([])

    with pytest.raises(ValueError, match="query cannot be empty"):
        service.retrieve(" \n ")

    embedder.embed_texts.assert_not_called()
    vector_store.count.assert_not_called()


def test_retrieval_config_validates_top_k_and_similarity_score() -> None:
    with pytest.raises(ValueError, match="top_k"):
        RetrievalConfig(top_k=0)
    with pytest.raises(ValueError, match="finite"):
        RetrievalConfig(minimum_similarity_score=float("nan"))
