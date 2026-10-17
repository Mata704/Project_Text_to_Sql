from types import SimpleNamespace

from text_to_sql.chat_pipeline import answer_relevant_questions
from text_to_sql.errors import LLMError
from text_to_sql.interaction_logs import InteractionLogService
from text_to_sql.llms.llm_selector.llm_selector_model import QuestionClassificationResult
from text_to_sql.retrieval import RetrievalConfig
from text_to_sql.usage_metrics import UsageMetricsService


def test_pipeline_interprets_all_results_once_after_individual_sql_processing(
    monkeypatch,
) -> None:
    retrieved_questions: list[str] = []
    generated_questions: list[str] = []
    interpreted_results: list[list[dict[str, object]]] = []

    class FakeRetrievalService:
        def __init__(self, **_kwargs) -> None:
            pass

        def retrieve(self, question: str):
            retrieved_questions.append(question)
            chunk = SimpleNamespace(
                chunk_id=f"chunk-{len(retrieved_questions)}",
                metadata={"source": "schema.md"},
                content="Informação de esquema.",
            )
            return [SimpleNamespace(chunk=chunk, score=0.9)]

    class FakeSQLiteService:
        pass

    class FakeSQLGeneratorService:
        def __init__(self, **_kwargs) -> None:
            pass

        def generate(self, question: str, _evidence):
            generated_questions.append(question)
            if question == "Qual o atraso médio?":
                raise LLMError("Não foi possível gerar uma query.")
            return SimpleNamespace(sql="SELECT 42 AS total;", parameters=[], citations=[])

    class FakeSQLExecutionService:
        def __init__(self, **_kwargs) -> None:
            pass

        def execute(self, **_kwargs):
            return SimpleNamespace(
                succeeded=True,
                rows=[{"total": 42}],
                attempts=1,
                error=None,
                sql="SELECT 42 AS total;",
                parameters={},
            )

    class FakeResultInterpreterService:
        def __init__(self, **_kwargs) -> None:
            pass

        def interpret(self, results):
            interpreted_results.append(list(results))
            return "42 viagens; o atraso médio não foi possível calcular."

    monkeypatch.setattr("text_to_sql.chat_pipeline.RetrievalService", FakeRetrievalService)
    monkeypatch.setattr("text_to_sql.chat_pipeline.SQLiteService", FakeSQLiteService)
    monkeypatch.setattr("text_to_sql.chat_pipeline.LLMSQLGeneratorService", FakeSQLGeneratorService)
    monkeypatch.setattr(
        "text_to_sql.chat_pipeline.SQLExecutionWithRetriesService",
        FakeSQLExecutionService,
    )
    monkeypatch.setattr(
        "text_to_sql.chat_pipeline.LLMResultInterpreterService",
        FakeResultInterpreterService,
    )

    interaction_logs = InteractionLogService()
    outcome = answer_relevant_questions(
        classifications=[
            QuestionClassificationResult(
                status="relevant",
                normalized_query="Quantas viagens foram realizadas?",
            ),
            QuestionClassificationResult(
                status="relevant",
                normalized_query="Qual o atraso médio?",
            ),
        ],
        settings=SimpleNamespace(openai_model="test-model"),
        api_key="test-key",
        retrieval_config=RetrievalConfig(),
        usage_metrics=UsageMetricsService(),
        interaction_logs=interaction_logs,
    )

    assert retrieved_questions == [
        "Quantas viagens foram realizadas?",
        "Qual o atraso médio?",
    ]
    assert generated_questions == retrieved_questions
    assert interpreted_results == [
        [
            {
                "question": "Quantas viagens foram realizadas?",
                "rows": [{"total": 42}],
                "failure": None,
            },
            {
                "question": "Qual o atraso médio?",
                "rows": [],
                "failure": "Não foi possível gerar uma query.",
            },
        ]
    ]
    assert outcome.answer == "42 viagens; o atraso médio não foi possível calcular."
    assert [evidence.rank for evidence in outcome.evidences] == [1]
    retrieval_log = next(
        entry for entry in interaction_logs.entries if entry.event == "retrieval_completed"
    )
    assert retrieval_log.details["results"] == [
        {
            "rank": 1,
            "source": "schema.md",
            "chunk_id": "chunk-1",
            "score": 0.9,
        }
    ]
