import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from text_to_sql.config import Settings
from text_to_sql.constants import (
    COMPONENT_RETRIEVAL,
    COMPONENT_SQL_EXECUTION,
    COMPONENT_SQL_GENERATOR,
    LOG_RESULT_ROWS_LIMIT,
    UNKNOWN_SOURCE,
)
from text_to_sql.errors import TextToSQLError
from text_to_sql.interaction_logs import InteractionEvidence, InteractionLogService
from text_to_sql.llms import LLMResultInterpreterService, LLMSQLGeneratorService
from text_to_sql.llms.llm_result_interpreter import QuestionResult
from text_to_sql.llms.llm_selector.llm_selector_model import QuestionClassificationResult
from text_to_sql.retrieval import RetrievalConfig, RetrievalService
from text_to_sql.sql_execution import SQLExecutionWithRetriesService
from text_to_sql.sqlite_db import SQLiteService
from text_to_sql.usage_metrics import UsageMetricsService


def _as_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


@dataclass
class PipelineOutcome:
    answer: str | None = None
    failure: str | None = None
    evidences: list[InteractionEvidence] = field(default_factory=list)


def answer_relevant_questions(
    *,
    classifications: Sequence[QuestionClassificationResult],
    settings: Settings,
    api_key: str,
    retrieval_config: RetrievalConfig,
    usage_metrics: UsageMetricsService,
    interaction_logs: InteractionLogService,
) -> PipelineOutcome:
    if not classifications:
        raise ValueError("At least one relevant question is required.")

    question_results: list[QuestionResult] = []
    evidences: list[InteractionEvidence] = []

    for classification in classifications:
        result, question_evidence = _process_relevant_question(
            classification=classification,
            settings=settings,
            api_key=api_key,
            retrieval_config=retrieval_config,
            usage_metrics=usage_metrics,
            interaction_logs=interaction_logs,
            evidence_rank_start=len(evidences) + 1,
        )
        question_results.append(result)
        evidences.extend(question_evidence)

    if all(result["failure"] is not None for result in question_results):
        failures = [result["failure"] for result in question_results if result["failure"]]
        return PipelineOutcome(
            failure=" ".join(failures),
            evidences=evidences,
        )

    answer = LLMResultInterpreterService(
        api_key=api_key,
        model=settings.openai_model,
        usage_metrics=usage_metrics,
    ).interpret(question_results)
    return PipelineOutcome(answer=answer, evidences=evidences)


def _process_relevant_question(
    *,
    classification: QuestionClassificationResult,
    settings: Settings,
    api_key: str,
    retrieval_config: RetrievalConfig,
    usage_metrics: UsageMetricsService,
    interaction_logs: InteractionLogService,
    evidence_rank_start: int,
) -> tuple[QuestionResult, list[InteractionEvidence]]:
    question = classification.normalized_query
    interaction_logs.record(
        level="info",
        component=COMPONENT_RETRIEVAL,
        event="retrieval_started",
        message="A pesquisa de evidências começou.",
        details={
            "top_k": retrieval_config.top_k,
            "minimum_similarity_score": retrieval_config.minimum_similarity_score,
            "question": question,
        },
    )
    try:
        retrieved_chunks = RetrievalService(
            api_key=api_key,
            config=retrieval_config,
            usage_metrics=usage_metrics,
        ).retrieve(question)
    except TextToSQLError as error:
        _record_question_failure(interaction_logs, question, error)
        return {"question": question, "rows": [], "failure": str(error)}, []
    interaction_logs.record(
        level="info",
        component=COMPONENT_RETRIEVAL,
        event="retrieval_completed",
        message="A pesquisa de evidências terminou.",
        details={
            "count": len(retrieved_chunks),
            "question": question,
            "results": [
                {
                    "rank": rank,
                    "source": str(result.chunk.metadata.get("source", UNKNOWN_SOURCE)),
                    "chunk_id": result.chunk.chunk_id,
                    "score": round(result.score, 4),
                }
                for rank, result in enumerate(retrieved_chunks, start=1)
            ],
        },
    )

    citations_by_chunk: dict[tuple[str, str], list[str]] = {}
    try:
        sqlite_service = SQLiteService()
        generation = LLMSQLGeneratorService(
            api_key=api_key,
            model=settings.openai_model,
            sqlite_service=sqlite_service,
            usage_metrics=usage_metrics,
            interaction_logs=interaction_logs,
        ).generate(question, retrieved_chunks)
    except TextToSQLError as error:
        interaction_logs.record(
            level="warning",
            component=COMPONENT_SQL_GENERATOR,
            event="generation_failed",
            message="A geração da query falhou após as tentativas permitidas.",
            details={"error": str(error), "question": question},
        )
        return {"question": question, "rows": [], "failure": str(error)}, []

    for citation in generation.citations:
        citations_by_chunk.setdefault((citation.source, citation.chunk_id), []).append(
            citation.quote
        )
    evidences = []
    for rank, result in enumerate(retrieved_chunks, start=evidence_rank_start):
        source = str(result.chunk.metadata.get("source", UNKNOWN_SOURCE))
        evidences.append(
            InteractionEvidence(
                rank=rank,
                question=question,
                source=source,
                chunk_id=result.chunk.chunk_id,
                score=result.score,
                content=result.chunk.content,
                citations=citations_by_chunk.get((source, result.chunk.chunk_id), []),
            )
        )

    if generation.sql is None:
        failure = generation.explanation or "Não foi possível gerar uma query."
        interaction_logs.record(
            level="warning",
            component=COMPONENT_SQL_GENERATOR,
            event="question_not_answerable",
            message="Não foi possível gerar uma query com as evidências disponíveis.",
            details={"question": question, "failure": failure},
        )
        return {"question": question, "rows": [], "failure": failure}, evidences

    parameters = {parameter.name: parameter.value for parameter in generation.parameters}
    interaction_logs.record(
        level="info",
        component=COMPONENT_SQL_EXECUTION,
        event="execution_started",
        message="A execução da query SELECT começou.",
        details={
            "sql": generation.sql,
            "parameters": _as_json(parameters),
            "question": question,
        },
    )
    try:
        execution = SQLExecutionWithRetriesService(
            api_key=api_key,
            model=settings.openai_model,
            sqlite_service=sqlite_service,
            usage_metrics=usage_metrics,
        ).execute(
            question=question,
            sql=generation.sql,
            parameters=parameters,
            evidence=retrieved_chunks,
        )
    except TextToSQLError as error:
        _record_question_failure(
            interaction_logs,
            question,
            error,
            component=COMPONENT_SQL_EXECUTION,
        )
        return {"question": question, "rows": [], "failure": str(error)}, evidences

    interaction_logs.record(
        level="info" if execution.succeeded else "error",
        component=COMPONENT_SQL_EXECUTION,
        event="execution_completed" if execution.succeeded else "execution_failed",
        message=(
            "A execução da query terminou."
            if execution.succeeded
            else (
                "A query não pôde ser executada após as tentativas permitidas. "
                f"Erro: {execution.error or 'erro SQL não especificado'}"
            )
        ),
        details={
            "attempts": execution.attempts,
            "error": execution.error,
            "final_sql": execution.sql,
            "final_parameters": _as_json(execution.parameters),
            "row_count": len(execution.rows),
            "rows": _as_json(execution.rows[:LOG_RESULT_ROWS_LIMIT]),
            "question": question,
        },
    )
    if not execution.succeeded:
        failure = (
            f"Não foi possível executar a query após {execution.attempts} tentativas. "
            f"Erro: {execution.error or 'erro SQL não especificado'}."
        )
        return {"question": question, "rows": [], "failure": failure}, evidences

    return {"question": question, "rows": execution.rows, "failure": None}, evidences


def _record_question_failure(
    interaction_logs: InteractionLogService,
    question: str,
    error: TextToSQLError,
    *,
    component: str = COMPONENT_RETRIEVAL,
) -> None:
    interaction_logs.record(
        level="error",
        component=component,
        event="question_processing_failed",
        message="Não foi possível processar esta pergunta.",
        details={"question": question, "error": str(error)},
    )
