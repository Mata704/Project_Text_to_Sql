from pathlib import Path
from unittest.mock import Mock

import pytest

from text_to_sql.document_ingestion import (
    DocumentIngestionConfig,
    DocumentIngestionService,
)
from text_to_sql.document_ingestion.document_ingestion_service import DocumentIngestionError
from text_to_sql.embeddings import EmbeddingConfig, TextEmbedding
from text_to_sql.vector_store import ChromaDBConfig, ChromaDBService


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.embed_texts = Mock(side_effect=self._embed_texts)

    def _embed_texts(self, texts: list[str]) -> list[TextEmbedding]:
        return [
            TextEmbedding(
                text=text,
                vector=[float(index + 1), 1.0],
                model="text-embedding-3-small",
                index=index,
            )
            for index, text in enumerate(texts)
        ]


def _service(
    documentation_directory: Path,
    database_directory: Path,
    embedder: FakeEmbeddingService,
) -> DocumentIngestionService:
    config = DocumentIngestionConfig(
        documentation_directory=documentation_directory,
        embedding=EmbeddingConfig(batch_size=2),
        vector_store=ChromaDBConfig(
            collection_name="ingestion_tests",
            persist_directory=database_directory,
        ),
    )
    return DocumentIngestionService(
        api_key="test-key",
        config=config,
        embedding_service=embedder,
    )


def test_ingestion_chunks_embeds_and_persists_markdown(tmp_path: Path) -> None:
    documentation_directory = tmp_path / "documentation"
    documentation_directory.mkdir()
    (documentation_directory / "trains.md").write_text(
        "# Comboios\n\n## Tipos\n\nExistem vários tipos de comboios.",
        encoding="utf-8",
    )
    embedder = FakeEmbeddingService()
    service = _service(documentation_directory, tmp_path / "chroma", embedder)

    result = service.run()

    assert result.skipped is False
    assert result.chunk_count == 1
    assert result.embedded_count == 1
    assert result.deleted_count == 0
    assert embedder.embed_texts.call_args.args == (
        ["# Comboios\n# Tipos\n\nExistem vários tipos de comboios."],
    )
    assert service.vector_store_service.count() == 1
    stored = service.vector_store_service.get_chunks(
        service.vector_store_service.get_all_chunk_ids()
    )
    assert stored[0].metadata["source"] == "trains.md"


def test_ingestion_skips_embedding_when_corpus_is_unchanged(tmp_path: Path) -> None:
    documentation_directory = tmp_path / "documentation"
    documentation_directory.mkdir()
    (documentation_directory / "trains.md").write_text("# Comboios\n\nTexto.", encoding="utf-8")
    database_directory = tmp_path / "chroma"
    first_embedder = FakeEmbeddingService()
    first_result = _service(documentation_directory, database_directory, first_embedder).run()

    second_embedder = FakeEmbeddingService()
    second_result = _service(documentation_directory, database_directory, second_embedder).run()

    assert first_result.skipped is False
    assert second_result.skipped is True
    assert first_result.fingerprint == second_result.fingerprint
    second_embedder.embed_texts.assert_not_called()


def test_ingestion_repairs_collection_with_missing_chunks(tmp_path: Path) -> None:
    documentation_directory = tmp_path / "documentation"
    documentation_directory.mkdir()
    (documentation_directory / "trains.md").write_text("# Comboios\n\nTexto.", encoding="utf-8")
    (documentation_directory / "stations.md").write_text("# Estações\n\nTexto.", encoding="utf-8")
    database_directory = tmp_path / "chroma"
    service = _service(documentation_directory, database_directory, FakeEmbeddingService())
    service.run()

    service.vector_store_service.delete_chunks(service.vector_store_service.get_all_chunk_ids()[:1])
    embedder = FakeEmbeddingService()
    result = _service(documentation_directory, database_directory, embedder).run()

    assert result.skipped is False
    assert result.chunk_count == 2
    assert result.embedded_count == 2
    assert (
        ChromaDBService(
            ChromaDBConfig(collection_name="ingestion_tests", persist_directory=database_directory)
        ).count()
        == 2
    )


def test_ingestion_updates_changed_docs_and_deletes_obsolete_chunks(tmp_path: Path) -> None:
    documentation_directory = tmp_path / "documentation"
    documentation_directory.mkdir()
    document_path = documentation_directory / "trains.md"
    document_path.write_text("# Comboios\n\nTexto original.", encoding="utf-8")
    database_directory = tmp_path / "chroma"
    _service(documentation_directory, database_directory, FakeEmbeddingService()).run()

    document_path.write_text("# Comboios\n\nTexto atualizado.", encoding="utf-8")
    embedder = FakeEmbeddingService()
    result = _service(documentation_directory, database_directory, embedder).run()
    store = ChromaDBService(
        ChromaDBConfig(collection_name="ingestion_tests", persist_directory=database_directory)
    )

    assert result.skipped is False
    assert result.embedded_count == 1
    assert result.deleted_count == 1
    assert store.count() == 1
    assert store.get_chunks(store.get_all_chunk_ids())[0].content.endswith("Texto atualizado.")


def test_ingestion_removes_chunks_for_deleted_documents(tmp_path: Path) -> None:
    documentation_directory = tmp_path / "documentation"
    documentation_directory.mkdir()
    document_path = documentation_directory / "trains.md"
    document_path.write_text("# Comboios\n\nTexto.", encoding="utf-8")
    database_directory = tmp_path / "chroma"
    _service(documentation_directory, database_directory, FakeEmbeddingService()).run()
    document_path.unlink()
    (documentation_directory / "other.md").write_text("# Outro\n\nNovo texto.", encoding="utf-8")

    result = _service(
        documentation_directory,
        database_directory,
        FakeEmbeddingService(),
    ).run()
    store = ChromaDBService(
        ChromaDBConfig(collection_name="ingestion_tests", persist_directory=database_directory)
    )

    assert result.deleted_count == 1
    assert store.count() == 1
    assert store.get_chunks(store.get_all_chunk_ids())[0].metadata["source"] == "other.md"


def test_ingestion_reports_missing_documentation_directory(tmp_path: Path) -> None:
    service = _service(
        tmp_path / "missing-documentation",
        tmp_path / "chroma",
        FakeEmbeddingService(),
    )

    with pytest.raises(DocumentIngestionError, match="Documentation directory does not exist"):
        service.run()
