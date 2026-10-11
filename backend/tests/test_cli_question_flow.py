from types import SimpleNamespace

import pytest
from pydantic import SecretStr

from text_to_sql.cli import main
from text_to_sql.document_ingestion import DocumentIngestionConfig


@pytest.mark.parametrize(
    ("status", "should_retrieve"),
    [
        ("relevant", True),
        ("irrelevant", False),
        ("ambiguous", False),
    ],
)
def test_cli_retrieves_only_relevant_questions(
    monkeypatch,
    capsys,
    status: str,
    should_retrieve: bool,
) -> None:
    calls: list[tuple[dict[str, object], str]] = []
    sqlite_instances = []

    class FakeSQLiteService:
        def __init__(self) -> None:
            sqlite_instances.append(self)

        def validate_select(self, query: str, parameters: dict[str, object]) -> None:
            calls.append(
                (
                    {"query": query, "parameters": parameters},
                    "sqlite-validate",
                )
            )

        def fetch_all(self, query: str, parameters: dict[str, object]):
            calls.append(({"query": query, "parameters": parameters}, "sqlite-fetch"))
            return [{"total_viagens": 42}]

    class FakeSampleDatabaseService:
        def ensure_current(self) -> bool:
            calls.append(({}, "database-ensure"))
            return False

    class FakeIngestionService:
        def __init__(self, api_key: str, config: DocumentIngestionConfig) -> None:
            calls.append(({"api_key": api_key, "config": config}, "ingestion-init"))

        def run(self):
            calls.append(({}, "ingestion-run"))
            return SimpleNamespace(skipped=True, chunk_count=0)

    class FakeSelectorService:
        def __init__(self, **kwargs: str) -> None:
            self.kwargs = kwargs

        def run(self, question: str) -> None:
            calls.append((self.kwargs, question))
            return SimpleNamespace(status=status, normalized_query="Pergunta normalizada?")

    class FakeRetrievalService:
        def __init__(self, api_key: str, config) -> None:
            calls.append(({"api_key": api_key, "config": config}, "retrieval-init"))

        def retrieve(self, question: str):
            calls.append(({}, question))
            chunk = SimpleNamespace(
                chunk_id="viagens-001",
                metadata={"source": "tables/viagens.md"},
                content="A documentação descreve as viagens.",
            )
            return [SimpleNamespace(chunk=chunk, score=0.91)]

    class FakeSQLGeneratorService:
        def __init__(self, api_key: str, model: str, sqlite_service) -> None:
            self.sqlite_service = sqlite_service
            calls.append(
                (
                    {
                        "api_key": api_key,
                        "model": model,
                        "sqlite_service": sqlite_service,
                    },
                    "sql-generator-init",
                )
            )

        def generate(self, question: str, evidence):
            calls.append(({"evidence": evidence}, question))
            parameters = {"state": "Realizada"}
            self.sqlite_service.validate_select(
                "SELECT COUNT(*) FROM viagens;",
                parameters,
            )
            return SimpleNamespace(
                explanation="Contagem de viagens.",
                sql="SELECT COUNT(*) FROM viagens;",
                parameters=[SimpleNamespace(name="state", value="Realizada")],
                citations=[
                    SimpleNamespace(
                        source="tables/viagens.md",
                        chunk_id="viagens-001",
                        quote="Descrição das viagens.",
                    )
                ],
            )

    class FakeResultInterpreterService:
        def __init__(self, api_key: str, model: str) -> None:
            calls.append(
                (
                    {"api_key": api_key, "model": model},
                    "result-interpreter-init",
                )
            )

        def interpret(self, question: str, rows: list[dict[str, object]]) -> str:
            calls.append(({"rows": rows}, question))
            return "Foram encontradas 42 viagens."

    monkeypatch.setattr(
        "text_to_sql.cli.DocumentIngestionService",
        FakeIngestionService,
    )
    monkeypatch.setattr(
        "text_to_sql.cli.SampleDatabaseService",
        FakeSampleDatabaseService,
    )
    monkeypatch.setattr(
        "text_to_sql.cli.Settings",
        lambda: SimpleNamespace(
            openai_api_key=SecretStr("test-key"),
            openai_model="test-model",
            openai_embedding_model="test-embedding-model",
        ),
    )
    monkeypatch.setattr(
        "text_to_sql.cli.LLMSelectorService",
        FakeSelectorService,
    )
    monkeypatch.setattr(
        "text_to_sql.cli.RetrievalService",
        FakeRetrievalService,
    )
    monkeypatch.setattr(
        "text_to_sql.cli.LLMSQLGeneratorService",
        FakeSQLGeneratorService,
    )
    monkeypatch.setattr(
        "text_to_sql.cli.LLMResultInterpreterService",
        FakeResultInterpreterService,
    )
    monkeypatch.setattr("text_to_sql.cli.SQLiteService", FakeSQLiteService)
    monkeypatch.setattr("builtins.input", lambda _prompt: "Quantas viagens?")

    assert main() == 0
    assert calls[0] == ({}, "database-ensure")
    assert calls[1][0]["api_key"] == "test-key"
    assert calls[1][0]["config"].embedding.model == "test-embedding-model"
    assert calls[1][1] == "ingestion-init"
    assert calls[2] == ({}, "ingestion-run")
    selector_call = (
        {"api_key": "test-key", "model": "test-model"},
        "Quantas viagens?",
    )
    assert calls[3] == selector_call
    captured = capsys.readouterr()
    output = captured.out
    assert ("retrieval-init" in [call[1] for call in calls]) is should_retrieve
    if should_retrieve:
        assert calls[4][0]["api_key"] == "test-key"
        assert calls[4][0]["config"].embedding.model == "test-embedding-model"
        assert calls[4][1] == "retrieval-init"
        assert calls[5] == ({}, "Pergunta normalizada?")
        assert calls[6] == (
            {
                "api_key": "test-key",
                "model": "test-model",
                "sqlite_service": sqlite_instances[0],
            },
            "sql-generator-init",
        )
        assert calls[7][1] == "Pergunta normalizada?"
        assert "Chunks recuperados:" in output
        assert "1. ID: viagens-001 | score: 0.910 | fonte: tables/viagens.md" in output
        assert "A documentação descreve as viagens." in output
        assert "Query SQL gerada:" in output
        assert calls[8] == (
            {
                "query": "SELECT COUNT(*) FROM viagens;",
                "parameters": {"state": "Realizada"},
            },
            "sqlite-validate",
        )
        assert calls[9] == (
            {
                "query": "SELECT COUNT(*) FROM viagens;",
                "parameters": {"state": "Realizada"},
            },
            "sqlite-fetch",
        )
        assert calls[10] == (
            {"api_key": "test-key", "model": "test-model"},
            "result-interpreter-init",
        )
        assert calls[11] == (
            {"rows": [{"total_viagens": 42}]},
            "Quantas viagens?",
        )
        assert "SELECT COUNT(*) FROM viagens;" in output
        assert "Foram encontradas 42 viagens." in output
        assert '"total_viagens": 42' not in output
        assert '"state": "Realizada"' in output
    else:
        assert len(calls) == 4
        assert "Chunks recuperados:" not in output
        assert "Não foram encontradas evidências" not in output
