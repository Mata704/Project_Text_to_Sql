from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from text_to_sql.api import create_app
from text_to_sql.document_ingestion import DocumentIngestionConfig


def _post_chat(question: str) -> tuple[int, dict]:
    with TestClient(create_app()) as client:
        reply = client.post("/chat", json={"question": question})
    return reply.status_code, reply.json()


def test_health_returns_ok(monkeypatch) -> None:
    monkeypatch.setattr("text_to_sql.api.server.prepare_runtime", lambda: None)
    with TestClient(create_app()) as client:
        reply = client.get("/health")
    assert reply.status_code == 200
    assert reply.json() == {"status": "ok"}


def test_chat_rejects_empty_question(monkeypatch) -> None:
    monkeypatch.setattr("text_to_sql.api.server.prepare_runtime", lambda: None)
    with TestClient(create_app()) as client:
        assert client.post("/chat", json={"question": "   "}).status_code == 422
        assert client.post("/chat", json={}).status_code == 422


@pytest.mark.parametrize("count", [0, 15])
def test_chat_passes_only_last_ten_history_messages(monkeypatch, count: int) -> None:
    received: list = []

    class FakeSelector:
        def __init__(self, **_kwargs) -> None:
            pass

        def run(self, _question: str, history=()):
            received.extend(history)
            return SimpleNamespace(
                status="irrelevant", normalized_query="fora", clarification_question=None
            )

    monkeypatch.setattr("text_to_sql.api.server.prepare_runtime", lambda: _fake_runtime())
    monkeypatch.setattr("text_to_sql.api.chat.LLMSelectorService", FakeSelector)
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(count)
    ]
    with TestClient(create_app()) as client:
        reply = client.post("/chat", json={"question": "olá", "history": history})
    assert reply.status_code == 200
    assert [m.content for m in received] == [f"m{i}" for i in range(count)][-10:]


def _fake_runtime():
    return SimpleNamespace(
        settings=SimpleNamespace(openai_model="m"),
        api_key="k",
        ingestion_config=None,
    )


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
        def __init__(
            self,
            api_key: str,
            config: DocumentIngestionConfig,
            usage_metrics=None,
        ) -> None:
            calls.append(({"api_key": api_key, "config": config}, "ingestion-init"))

        def run(self):
            calls.append(({}, "ingestion-run"))
            return SimpleNamespace(skipped=True, chunk_count=0, embedded_count=0)

    class FakeSelectorService:
        def __init__(
            self,
            api_key: str,
            model: str,
            usage_metrics=None,
            interaction_logs=None,
        ) -> None:
            self.kwargs = {"api_key": api_key, "model": model}
            self.usage_metrics = usage_metrics
            self.interaction_logs = interaction_logs

        def run(self, question: str, history=()) -> None:
            calls.append((self.kwargs, question))
            self.usage_metrics.record_call(
                component="question_classifier",
                model="test-model",
                usage=SimpleNamespace(input_tokens=10, output_tokens=2, total_tokens=12),
                elapsed_seconds=0.01,
            )
            self.interaction_logs.record(
                level="info",
                component="question_classifier",
                event="question_classified",
                message="A pergunta foi classificada.",
                details={"status": status},
            )
            return SimpleNamespace(
                status=status,
                normalized_query="Pergunta normalizada?",
                clarification_question="Que data?" if status == "ambiguous" else None,
            )

    class FakeRetrievalService:
        def __init__(self, api_key: str, config, usage_metrics=None) -> None:
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
        def __init__(
            self,
            api_key: str,
            model: str,
            sqlite_service,
            usage_metrics=None,
            interaction_logs=None,
        ) -> None:
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
        def __init__(self, api_key: str, model: str, usage_metrics=None) -> None:
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
        "text_to_sql.api.chat.DocumentIngestionService",
        FakeIngestionService,
    )
    monkeypatch.setattr(
        "text_to_sql.api.chat.SampleDatabaseService",
        FakeSampleDatabaseService,
    )
    monkeypatch.setattr(
        "text_to_sql.api.chat.Settings",
        lambda: SimpleNamespace(
            openai_api_key=SecretStr("test-key"),
            openai_model="test-model",
            openai_embedding_model="test-embedding-model",
        ),
    )
    monkeypatch.setattr(
        "text_to_sql.api.chat.LLMSelectorService",
        FakeSelectorService,
    )
    monkeypatch.setattr(
        "text_to_sql.chat_pipeline.RetrievalService",
        FakeRetrievalService,
    )
    monkeypatch.setattr(
        "text_to_sql.chat_pipeline.LLMSQLGeneratorService",
        FakeSQLGeneratorService,
    )
    monkeypatch.setattr(
        "text_to_sql.chat_pipeline.LLMResultInterpreterService",
        FakeResultInterpreterService,
    )
    monkeypatch.setattr("text_to_sql.chat_pipeline.SQLiteService", FakeSQLiteService)

    status_code, response = _post_chat("Quantas viagens?")
    assert status_code == 200
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
        assert response["role"] == "assistant"
        assert response["question"] == "Quantas viagens?"
        assert response["answer"] == "Foram encontradas 42 viagens."
        assert response["sessionId"] == response["usageMetrics"]["session_id"]
        assert response["evidence"] == [
            {
                "rank": 1,
                "source": "tables/viagens.md",
                "chunk_id": "viagens-001",
                "score": 0.91,
                "content": "A documentação descreve as viagens.",
                "citations": ["Descrição das viagens."],
            }
        ]
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
        assert response["usageMetrics"]["total"]["calls"] == 1
        assert "question_classifier" in response["usageMetrics"]["components"]
        assert response["error"] is None
    else:
        assert len(calls) == 4
        assert response["evidence"] == []
        assert response["answer"] == (
            "Que data?" if status == "ambiguous" else "Pergunta normalizada?"
        )


def test_chat_includes_sqlite_failure_reason_in_response_and_logs(monkeypatch) -> None:
    question = "Qual o combóio com maior atraso?"
    sqlite_error = "Could not read from SQLite: no such column: atraso"

    class FakeIngestionService:
        def __init__(self, **_kwargs) -> None:
            pass

        def run(self):
            return SimpleNamespace(skipped=True, chunk_count=0, embedded_count=0)

    class FakeSelectorService:
        def __init__(self, **_kwargs) -> None:
            pass

        def run(self, _question: str, _history=()):
            return SimpleNamespace(status="relevant", normalized_query=question)

    class FakeRetrievalService:
        def __init__(self, **_kwargs) -> None:
            pass

        def retrieve(self, _question: str):
            chunk = SimpleNamespace(
                chunk_id="delays-001",
                metadata={"source": "sql-examples/02-atrasos.md"},
                content="Atrasos de chegada por comboio.",
            )
            return [SimpleNamespace(chunk=chunk, score=0.9)]

    class FakeSQLiteService:
        def validate_select(self, _sql: str, _parameters: dict[str, object]) -> None:
            pass

    class FakeSQLGeneratorService:
        def __init__(self, **_kwargs) -> None:
            pass

        def generate(self, _question: str, _evidence):
            return SimpleNamespace(
                sql="SELECT atraso FROM viagens;",
                parameters=[],
                citations=[],
            )

    class FakeSQLExecutionService:
        def __init__(self, **_kwargs) -> None:
            pass

        def execute(self, **_kwargs):
            return SimpleNamespace(
                succeeded=False,
                attempts=3,
                error=sqlite_error,
            )

    monkeypatch.setattr(
        "text_to_sql.api.chat.Settings",
        lambda: SimpleNamespace(
            openai_api_key=SecretStr("test-key"),
            openai_model="test-model",
            openai_embedding_model="test-embedding-model",
        ),
    )
    monkeypatch.setattr(
        "text_to_sql.api.chat.SampleDatabaseService",
        lambda: SimpleNamespace(ensure_current=lambda: False),
    )
    monkeypatch.setattr("text_to_sql.api.chat.DocumentIngestionService", FakeIngestionService)
    monkeypatch.setattr("text_to_sql.api.chat.LLMSelectorService", FakeSelectorService)
    monkeypatch.setattr("text_to_sql.chat_pipeline.RetrievalService", FakeRetrievalService)
    monkeypatch.setattr("text_to_sql.chat_pipeline.SQLiteService", FakeSQLiteService)
    monkeypatch.setattr("text_to_sql.chat_pipeline.LLMSQLGeneratorService", FakeSQLGeneratorService)
    monkeypatch.setattr(
        "text_to_sql.chat_pipeline.SQLExecutionWithRetriesService",
        FakeSQLExecutionService,
    )

    status_code, response = _post_chat(question)
    assert status_code == 422

    assert response["question"] == question
    assert response["answer"] is None
    assert response["error"] == (
        "Não foi possível executar a query após 3 tentativas. "
        f"Erro: {sqlite_error}. Reformule a pergunta."
    )
    execution_log = next(log for log in response["logs"] if log["event"] == "execution_failed")
    assert execution_log["details"] == {
        "attempts": 3,
        "error": sqlite_error,
    }
