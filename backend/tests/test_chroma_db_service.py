from pathlib import Path

import pytest

from text_to_sql.chunking import DocumentChunk
from text_to_sql.embeddings import TextEmbedding
from text_to_sql.errors import VectorStoreError
from text_to_sql.vector_store import ChromaDBConfig, ChromaDBService


def make_chunk(chunk_id: str, content: str, chunk_index: int) -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        content=content,
        source="tables/viagens.md",
        document_title="Viagens",
        section_path=("Viagens",),
        chunk_index=chunk_index,
        total_chunks=2,
        start_line=chunk_index + 1,
        end_line=chunk_index + 1,
        token_count=2,
    )


def make_embedding(text: str, vector: list[float], index: int) -> TextEmbedding:
    return TextEmbedding(
        text=text,
        vector=vector,
        model="text-embedding-3-small",
        index=index,
    )


def test_chroma_upserts_reads_and_searches_persistent_chunks(tmp_path: Path) -> None:
    config = ChromaDBConfig(
        collection_name="test_trains",
        persist_directory=tmp_path / "chroma",
        batch_size=1,
    )
    service = ChromaDBService(config)
    chunks = [
        make_chunk("chunk-1", "Viagens de comboio", 0),
        make_chunk("chunk-2", "Atrasos das viagens", 1),
    ]
    embeddings = [
        make_embedding(chunks[0].content, [1.0, 0.0], 0),
        make_embedding(chunks[1].content, [0.0, 1.0], 1),
    ]

    assert service.upsert_chunks(chunks, embeddings) == 2
    assert service.count() == 2

    stored = service.get_chunks(["chunk-2", "missing", "chunk-1"])
    assert [chunk.chunk_id for chunk in stored] == ["chunk-2", "chunk-1"]
    assert stored[0].content == "Atrasos das viagens"
    assert stored[0].metadata["source"] == "tables/viagens.md"
    assert stored[0].metadata["start_line"] == 2

    results = service.search([0.9, 0.1], limit=1)
    assert len(results) == 1
    assert results[0].chunk_id == "chunk-1"
    assert results[0].distance is not None

    reopened_service = ChromaDBService(config)
    assert reopened_service.count() == 2
    assert reopened_service.get_chunks(["chunk-1"])[0].content == "Viagens de comboio"


def test_chroma_upsert_updates_existing_chunk(tmp_path: Path) -> None:
    service = ChromaDBService(
        ChromaDBConfig(
            collection_name="test_upsert_update",
            persist_directory=tmp_path / "chroma",
        )
    )
    chunk = make_chunk("same-id", "Versão inicial", 0)
    embedding = make_embedding(chunk.content, [1.0, 0.0], 0)
    service.upsert_chunks([chunk], [embedding])

    updated_chunk = make_chunk("same-id", "Versão atualizada", 0)
    updated_embedding = make_embedding(updated_chunk.content, [0.0, 1.0], 0)
    service.upsert_chunks([updated_chunk], [updated_embedding])

    assert service.count() == 1
    assert service.get_chunks(["same-id"])[0].content == "Versão atualizada"


def test_chroma_rejects_mismatched_chunk_and_embedding_inputs(tmp_path: Path) -> None:
    service = ChromaDBService(
        ChromaDBConfig(collection_name="test_invalid_upsert", persist_directory=tmp_path)
    )
    chunk = make_chunk("chunk-1", "Chunk de exemplo", 0)

    with pytest.raises(ValueError, match="exactly one embedding"):
        service.upsert_chunks([chunk], [])
    with pytest.raises(ValueError, match="do not match"):
        service.upsert_chunks([chunk], [make_embedding("outro texto", [1.0], 0)])
    with pytest.raises(ValueError, match="unique"):
        service.upsert_chunks(
            [chunk, chunk],
            [
                make_embedding(chunk.content, [1.0], 0),
                make_embedding(chunk.content, [1.0], 1),
            ],
        )


def test_chroma_requires_one_embedding_model_and_dimension_per_upsert(tmp_path: Path) -> None:
    service = ChromaDBService(
        ChromaDBConfig(collection_name="test_embedding_validation", persist_directory=tmp_path)
    )
    first_chunk = make_chunk("chunk-1", "Texto um", 0)
    second_chunk = make_chunk("chunk-2", "Texto dois", 1)

    with pytest.raises(ValueError, match="same model"):
        service.upsert_chunks(
            [first_chunk, second_chunk],
            [
                make_embedding(first_chunk.content, [1.0], 0),
                TextEmbedding(
                    text=second_chunk.content,
                    vector=[0.0],
                    model="other-model",
                    index=1,
                ),
            ],
        )
    with pytest.raises(ValueError, match="same dimension"):
        service.upsert_chunks(
            [first_chunk, second_chunk],
            [
                make_embedding(first_chunk.content, [1.0], 0),
                make_embedding(second_chunk.content, [0.0, 1.0], 1),
            ],
        )


def test_chroma_rejects_collection_embedding_model_mismatch(tmp_path: Path) -> None:
    config = ChromaDBConfig(collection_name="test_model_mismatch", persist_directory=tmp_path)
    service = ChromaDBService(config)
    chunk = make_chunk("chunk-1", "Texto", 0)
    service.upsert_chunks([chunk], [make_embedding(chunk.content, [1.0], 0)])

    with pytest.raises(VectorStoreError, match="uses embedding model"):
        service.upsert_chunks(
            [chunk],
            [
                TextEmbedding(
                    text=chunk.content,
                    vector=[1.0],
                    model="another-model",
                    index=0,
                )
            ],
        )


def test_chroma_empty_calls_and_search_validation(tmp_path: Path) -> None:
    service = ChromaDBService(
        ChromaDBConfig(collection_name="test_empty", persist_directory=tmp_path)
    )

    assert service.upsert_chunks([], []) == 0
    assert service.get_chunks([]) == []
    assert service.search([1.0, 0.0]) == []

    with pytest.raises(ValueError, match="cannot be empty"):
        service.search([])
    with pytest.raises(ValueError, match="at least 1"):
        service.search([1.0], limit=0)
    with pytest.raises(ValueError, match="finite values"):
        service.search([float("nan")])
