from dataclasses import dataclass

from text_to_sql.chat_pipeline import answer_relevant_question
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


@dataclass(frozen=True)
class ChatRuntime:
    settings: Settings
    api_key: str
    ingestion_config: DocumentIngestionConfig


def prepare_runtime() -> ChatRuntime:
    """Sincroniza a base de dados e a documentação RAG; corre uma vez no arranque."""
    settings = Settings()
    SampleDatabaseService().ensure_current()

    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value().strip():
        raise ConfigurationError("OPENAI_API_KEY is missing. Set it in .env or in the environment.")
    api_key = settings.openai_api_key.get_secret_value()

    ingestion_config = DocumentIngestionConfig(
        embedding=EmbeddingConfig(model=settings.openai_embedding_model)
    )
    DocumentIngestionService(api_key=api_key, config=ingestion_config).run()
    return ChatRuntime(settings=settings, api_key=api_key, ingestion_config=ingestion_config)


def answer_chat(question: str, runtime: ChatRuntime) -> InteractionResponse:
    interaction_logs = InteractionLogService()
    usage_metrics = UsageMetricsService(session_id=interaction_logs.session_id)
    answer: str | None = None
    error_message: str | None = None
    evidences: list[InteractionEvidence] = []

    try:
        classification = LLMSelectorService(
            api_key=runtime.api_key,
            model=runtime.settings.openai_model,
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
                level="info",
                component="interaction",
                event="clarification_requested",
                message="Foi pedida uma clarificação ao utilizador.",
            )
        else:
            outcome = answer_relevant_question(
                question=question,
                classification=classification,
                settings=runtime.settings,
                api_key=runtime.api_key,
                retrieval_config=RetrievalConfig(
                    embedding=runtime.ingestion_config.embedding,
                    vector_store=runtime.ingestion_config.vector_store,
                ),
                usage_metrics=usage_metrics,
                interaction_logs=interaction_logs,
            )
            evidences = outcome.evidences
            if outcome.failure is None:
                answer = outcome.answer
            else:
                error_message = f"{outcome.failure} Reformule a pergunta."
    except (ValueError, TextToSQLError) as error:
        error_message = str(error)
        interaction_logs.record(
            level="error",
            component="interaction",
            event="interaction_failed",
            message="A interação terminou com um erro.",
            details={"error": error_message},
        )

    return InteractionResponse(
        session_id=interaction_logs.session_id,
        question=question,
        answer=answer,
        evidence=evidences,
        usage_metrics=usage_metrics.snapshot(),
        logs=interaction_logs.entries,
        error=error_message,
    )
