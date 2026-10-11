from dataclasses import dataclass, field

from text_to_sql.config import Settings
from text_to_sql.errors import LLMError
from text_to_sql.interaction_logs import InteractionEvidence, InteractionLogService
from text_to_sql.llms import LLMResultInterpreterService, LLMSQLGeneratorService
from text_to_sql.llms.common import OpenAIRequestError
from text_to_sql.llms.llm_selector.llm_selector_model import QuestionClassificationResult
from text_to_sql.retrieval import RetrievalConfig, RetrievalService
from text_to_sql.sql_execution import SQLExecutionWithRetriesService
from text_to_sql.sqlite_db import SQLiteService
from text_to_sql.usage_metrics import UsageMetricsService


@dataclass
class PipelineOutcome:
    answer: str | None = None
    # Quando preenchido, o fluxo falhou após os retries e deve voltar à classificação.
    failure: str | None = None
    evidences: list[InteractionEvidence] = field(default_factory=list)


def answer_relevant_question(
    *,
    question: str,
    classification: QuestionClassificationResult,
    settings: Settings,
    api_key: str,
    retrieval_config: RetrievalConfig,
    usage_metrics: UsageMetricsService,
    interaction_logs: InteractionLogService,
) -> PipelineOutcome:
    interaction_logs.record(
        level="info",
        component="retrieval",
        event="retrieval_started",
        message="A pesquisa de evidências começou.",
        details={"top_k": retrieval_config.top_k},
    )
    retrieved_chunks = RetrievalService(
        api_key=api_key,
        config=retrieval_config,
        usage_metrics=usage_metrics,
    ).retrieve(classification.normalized_query)
    interaction_logs.record(
        level="info",
        component="retrieval",
        event="retrieval_completed",
        message="A pesquisa de evidências terminou.",
        details={"count": len(retrieved_chunks)},
    )

    sqlite_service = SQLiteService()
    try:
        generation = LLMSQLGeneratorService(
            api_key=api_key,
            model=settings.openai_model,
            sqlite_service=sqlite_service,
            usage_metrics=usage_metrics,
            interaction_logs=interaction_logs,
        ).generate(classification.normalized_query, retrieved_chunks)
    except OpenAIRequestError:
        raise
    except LLMError as error:
        interaction_logs.record(
            level="warning",
            component="sql_generator",
            event="generation_failed",
            message="A geração da query falhou após as tentativas permitidas.",
            details={"error": str(error)},
        )
        return PipelineOutcome(failure=str(error))

    citations_by_chunk: dict[tuple[str, str], list[str]] = {}
    for citation in generation.citations:
        citations_by_chunk.setdefault((citation.source, citation.chunk_id), []).append(
            citation.quote
        )
    evidences = [
        InteractionEvidence(
            rank=rank,
            source=str(result.chunk.metadata.get("source", "unknown")),
            chunk_id=result.chunk.chunk_id,
            score=result.score,
            content=result.chunk.content,
            citations=citations_by_chunk.get(
                (
                    str(result.chunk.metadata.get("source", "unknown")),
                    result.chunk.chunk_id,
                ),
                [],
            ),
        )
        for rank, result in enumerate(retrieved_chunks, start=1)
    ]

    if generation.sql is None:
        interaction_logs.record(
            level="warning",
            component="sql_generator",
            event="question_not_answerable",
            message="Não foi possível gerar uma query com as evidências disponíveis.",
        )
        return PipelineOutcome(
            failure=generation.explanation or "Não foi possível gerar uma query.",
            evidences=evidences,
        )

    parameters = {parameter.name: parameter.value for parameter in generation.parameters}
    interaction_logs.record(
        level="info",
        component="sql_execution",
        event="execution_started",
        message="A execução da query SELECT começou.",
    )
    execution = SQLExecutionWithRetriesService(
        api_key=api_key,
        model=settings.openai_model,
        sqlite_service=sqlite_service,
        usage_metrics=usage_metrics,
    ).execute(
        question=classification.normalized_query,
        sql=generation.sql,
        parameters=parameters,
        evidence=retrieved_chunks,
    )
    interaction_logs.record(
        level="info" if execution.succeeded else "error",
        component="sql_execution",
        event="execution_completed" if execution.succeeded else "execution_failed",
        message=(
            "A execução da query terminou."
            if execution.succeeded
            else (
                "A query não pôde ser executada após as tentativas permitidas. "
                f"Erro: {execution.error or 'erro SQL não especificado'}"
            )
        ),
        details={"attempts": execution.attempts, "error": execution.error},
    )
    if not execution.succeeded:
        return PipelineOutcome(
            failure=(
                f"Não foi possível executar a query após {execution.attempts} tentativas. "
                f"Erro: {execution.error or 'erro SQL não especificado'}."
            ),
            evidences=evidences,
        )

    answer = LLMResultInterpreterService(
        api_key=api_key,
        model=settings.openai_model,
        usage_metrics=usage_metrics,
    ).interpret(question, execution.rows)
    return PipelineOutcome(answer=answer, evidences=evidences)
