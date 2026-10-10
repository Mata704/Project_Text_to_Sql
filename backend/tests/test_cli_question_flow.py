from types import SimpleNamespace

from pydantic import SecretStr

from text_to_sql.cli import main
from text_to_sql.document_ingestion import DocumentIngestionConfig


def test_cli_only_constructs_and_calls_selector_service(monkeypatch) -> None:
    calls: list[tuple[dict[str, object], str]] = []

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
    monkeypatch.setattr("builtins.input", lambda _prompt: "Quantas viagens?")

    assert main() == 0
    assert calls[0] == ({}, "database-ensure")
    assert calls[1][0]["api_key"] == "test-key"
    assert calls[1][0]["config"].embedding.model == "test-embedding-model"
    assert calls[1][1] == "ingestion-init"
    assert calls[2] == ({}, "ingestion-run")
    assert calls[3] == (
        {"api_key": "test-key", "model": "test-model"},
        "Quantas viagens?",
    )
