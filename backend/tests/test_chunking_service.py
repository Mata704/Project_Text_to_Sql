from pathlib import Path

import pytest
import tiktoken

from text_to_sql.chunking import ChunkingConfig, ChunkingService


def test_chunking_preserves_section_path_and_source_metadata() -> None:
    service = ChunkingService()

    chunks = service.chunk_markdown(
        source="viagens.md",
        content="# Viagens\n\n## Horários\n\nA viagem tem uma hora de partida prevista.",
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.source == "viagens.md"
    assert chunk.document_title == "Viagens"
    assert chunk.section_path == ("Viagens", "Horários")
    assert (chunk.start_line, chunk.end_line) == (5, 5)
    assert chunk.chunk_index == 0
    assert chunk.total_chunks == 1
    assert chunk.token_count == len(tiktoken.get_encoding("cl100k_base").encode(chunk.content))
    assert chunk.content.startswith("# Viagens\n# Horários")
    assert chunk.metadata == {
        "source": "viagens.md",
        "document_title": "Viagens",
        "section": "Viagens > Horários",
        "chunk_index": 0,
        "total_chunks": 1,
        "start_line": 5,
        "end_line": 5,
        "token_count": chunk.token_count,
    }
    assert (
        chunk.chunk_id
        == service.chunk_markdown(
            source="viagens.md",
            content="# Viagens\n\n## Horários\n\nA viagem tem uma hora de partida prevista.",
        )[0].chunk_id
    )


def test_long_markdown_is_split_at_sentence_boundaries_with_overlap() -> None:
    service = ChunkingService(ChunkingConfig(max_chunk_chars=120, overlap_chars=45))
    content = " ".join(
        f"Este é o parágrafo número {index} sobre horários e viagens." for index in range(8)
    )

    chunks = service.chunk_markdown(source="horarios.md", content=content)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 120 for chunk in chunks)
    assert any(
        previous.content.splitlines()[-1] == current.content.splitlines()[-1]
        or previous.content.splitlines()[-1] in current.content
        for previous, current in zip(chunks, chunks[1:], strict=False)
    )
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.total_chunks for chunk in chunks} == {len(chunks)}
    assert all((chunk.start_line, chunk.end_line) == (1, 1) for chunk in chunks)


def test_large_markdown_table_repeats_header_when_split() -> None:
    service = ChunkingService(ChunkingConfig(max_chunk_chars=110, overlap_chars=0))
    rows = "\n".join(
        f"| `{index}` | Uma descrição de campo longa número {index} |" for index in range(1, 8)
    )
    content = f"# Viagens\n\n| Campo | Descrição |\n|---|---|\n{rows}"

    chunks = service.chunk_markdown(source="viagens.md", content=content)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= 110
        assert "| Campo | Descrição |" in chunk.content
        assert "|---|---|" in chunk.content
        assert chunk.start_line == 3
        assert chunk.end_line >= chunk.start_line
    assert {chunk.total_chunks for chunk in chunks} == {len(chunks)}


def test_document_title_falls_back_to_markdown_filename() -> None:
    chunks = ChunkingService().chunk_markdown(
        source="schema/viagens.md",
        content="Texto sem título.",
    )

    assert chunks[0].document_title == "viagens"


def test_code_block_chunks_track_source_lines() -> None:
    service = ChunkingService(ChunkingConfig(max_chunk_chars=45, overlap_chars=0))
    content = "# Código\n\n```sql\nSELECT 1;\nSELECT 2;\nSELECT 3;\n```"

    chunks = service.chunk_markdown(source="query.md", content=content)

    assert len(chunks) > 1
    assert chunks[0].start_line == 3
    assert chunks[-1].end_line == 7
    assert all(chunk.end_line >= chunk.start_line for chunk in chunks)


def test_heading_inside_fenced_code_is_not_treated_as_section() -> None:
    content = "# Exemplo\n\n```markdown\n## Não é um título\n```\n\nTexto."

    chunks = ChunkingService().chunk_markdown(source="exemplo.md", content=content)

    assert len(chunks) == 1
    assert chunks[0].section_path == ("Exemplo",)
    assert "## Não é um título" in chunks[0].content


def test_chunk_file_and_directory_read_markdown(tmp_path: Path) -> None:
    docs_dir = tmp_path / "docs"
    nested_dir = docs_dir / "schema"
    nested_dir.mkdir(parents=True)
    first_doc = docs_dir / "overview.md"
    second_doc = nested_dir / "viagens.md"
    first_doc.write_text("# Geral\n\nDocumento geral.", encoding="utf-8")
    second_doc.write_text("# Viagens\n\nDocumento de viagens.", encoding="utf-8")
    (docs_dir / "ignore.txt").write_text("Ignorar.", encoding="utf-8")
    service = ChunkingService()

    file_chunks = service.chunk_file(second_doc)
    directory_chunks = service.chunk_directory(docs_dir)

    assert file_chunks[0].source == "viagens.md"
    assert [chunk.source for chunk in directory_chunks] == [
        "overview.md",
        "schema/viagens.md",
    ]


def test_backend_documentation_chunks_within_configured_size() -> None:
    documentation_dir = Path(__file__).parents[1] / "documentation"

    chunks = ChunkingService().chunk_directory(documentation_dir)

    assert chunks
    assert all(len(chunk.content) <= 2400 for chunk in chunks)
    assert {chunk.source for chunk in chunks} >= {
        "01-schema.md",
        "tables/viagens.md",
        "sql-examples/01-viagens.md",
    }


def test_chunking_rejects_empty_content_and_invalid_sources() -> None:
    service = ChunkingService()

    with pytest.raises(ValueError, match="source cannot be empty"):
        service.chunk_markdown(source=" ", content="Texto.")
    with pytest.raises(ValueError, match="document is empty"):
        service.chunk_markdown(source="empty.md", content=" \n")


def test_chunking_validates_overlap_size() -> None:
    with pytest.raises(ValueError, match="overlap_chars must be smaller"):
        ChunkingConfig(max_chunk_chars=100, overlap_chars=100)


def test_chunk_file_reports_missing_or_unsupported_documents(tmp_path: Path) -> None:
    service = ChunkingService()

    with pytest.raises(FileNotFoundError, match="does not exist"):
        service.chunk_file(tmp_path / "missing.md")

    text_file = tmp_path / "document.txt"
    text_file.write_text("Conteúdo.", encoding="utf-8")
    with pytest.raises(ValueError, match="Only Markdown"):
        service.chunk_file(text_file)
