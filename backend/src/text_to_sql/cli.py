import sys

from text_to_sql.cli_pipeline import answer_relevant_question
from text_to_sql.config import Settings
from text_to_sql.document_ingestion import DocumentIngestionConfig, DocumentIngestionService
from text_to_sql.embeddings import EmbeddingConfig
from text_to_sql.errors import ConfigurationError, TextToSQLError
from text_to_sql.interaction_logs import (
    InteractionEvidence,
    InteractionLogService,
    InteractionResponse,
)
from text_to_sql.llms import LLMSelectorService
from text_to_sql.retrieval import RetrievalConfig
from text_to_sql.sample_database import SampleDatabaseService
from text_to_sql.usage_metrics import UsageMetricsService


def main() -> int:
    interaction_logs = InteractionLogService()
    usage_metrics = UsageMetricsService(session_id=interaction_logs.session_id)
    question: str | None = None
    answer: str | None = None
    error_message: str | None = None
    evidences: list[InteractionEvidence] = []
    exit_code = 0

    try:
        settings = Settings()
        interaction_logs.record(
            level="info",
            component="sample_database",
            event="synchronization_started",
            message="A sincronização da base de dados de demonstração começou.",
        )
        database_changed = SampleDatabaseService().ensure_current()
        interaction_logs.record(
            level="info",
            component="sample_database",
            event="synchronization_completed",
            message="A base de dados de demonstração está pronta.",
            details={"changed": database_changed},
        )

        if (
            settings.openai_api_key is None
            or not settings.openai_api_key.get_secret_value().strip()
        ):
            raise ConfigurationError(
                "OPENAI_API_KEY is missing. Set it in .env or in the environment."
            )
        api_key = settings.openai_api_key.get_secret_value()

        ingestion_config = DocumentIngestionConfig(
            embedding=EmbeddingConfig(model=settings.openai_embedding_model)
        )
        interaction_logs.record(
            level="info",
            component="document_ingestion",
            event="ingestion_started",
            message="A sincronização da documentação RAG começou.",
        )
        ingestion_result = DocumentIngestionService(
            api_key=api_key,
            config=ingestion_config,
            usage_metrics=usage_metrics,
        ).run()
        interaction_logs.record(
            level="info",
            component="document_ingestion",
            event="ingestion_completed",
            message="A sincronização da documentação RAG terminou.",
            details={
                "skipped": ingestion_result.skipped,
                "chunks": ingestion_result.chunk_count,
                "embedded_chunks": ingestion_result.embedded_count,
            },
        )

        sys.stderr.write("Pergunta sobre viagens de comboio: ")
        sys.stderr.flush()
        question = input("").strip()
        if not question:
            raise ValueError("The question cannot be empty.")

        classification = LLMSelectorService(
            api_key=api_key,
            model=settings.openai_model,
            usage_metrics=usage_metrics,
            interaction_logs=interaction_logs,
        ).run(question)

        if classification.status == "irrelevant":
            answer = classification.normalized_query
            interaction_logs.record(
                level="info",
                component="interaction",
                event="out_of_scope_answer",
                message="Foi devolvida a resposta para uma pergunta fora do âmbito.",
            )
        elif classification.status == "ambiguous":
            # Só o classificador pode fazer perguntas ao utilizador.
            answer = classification.clarification_question
            interaction_logs.record(
                level="warning",
                component="interaction",
                event="clarification_unresolved",
                message="A pergunta permaneceu ambígua após as clarificações.",
            )
        else:
            outcome = answer_relevant_question(
                question=question,
                classification=classification,
                settings=settings,
                api_key=api_key,
                retrieval_config=RetrievalConfig(
                    embedding=ingestion_config.embedding,
                    vector_store=ingestion_config.vector_store,
                ),
                usage_metrics=usage_metrics,
                interaction_logs=interaction_logs,
            )
            evidences = outcome.evidences
            if outcome.failure is None:
                answer = outcome.answer
            else:
                error_message = f"{outcome.failure} Reformule a pergunta."
                exit_code = 1
    except (ValueError, TextToSQLError) as error:
        error_message = str(error)
        exit_code = 1
        interaction_logs.record(
            level="error",
            component="interaction",
            event="interaction_failed",
            message="A interação terminou com um erro.",
            details={"error": error_message},
        )

    response = InteractionResponse(
        session_id=interaction_logs.session_id,
        question=question,
        answer=answer,
        evidence=evidences,
        usage_metrics=usage_metrics.snapshot(),
        logs=interaction_logs.entries,
        error=error_message,
    )
    sys.stdout.write(response.model_dump_json(by_alias=True, indent=2) + "\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
