from collections.abc import Sequence
from dataclasses import dataclass

from text_to_sql.api.constants import HISTORY_MESSAGES_LIMIT
from text_to_sql.chat_pipeline import answer_relevant_questions
from text_to_sql.config import Settings
from text_to_sql.constants import COMPONENT_INTERACTION
from text_to_sql.document_ingestion import DocumentIngestionConfig, DocumentIngestionService
from text_to_sql.embeddings import EmbeddingConfig
from text_to_sql.entity_resolution import EntityResolutionService
from text_to_sql.errors import ConfigurationError, TextToSQLError
from text_to_sql.interaction_logs import (
    InteractionEvidence,
    InteractionLogService,
    InteractionResponse,
)
from text_to_sql.llms import LLMSelectorService
from text_to_sql.llms.llm_selector import ConversationMessage
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


def answer_chat(
    question: str,
    runtime: ChatRuntime,
    history: Sequence[ConversationMessage] = (),
    session_id: str | None = None,
) -> InteractionResponse:
    interaction_logs = InteractionLogService(session_id=session_id)
    usage_metrics = UsageMetricsService(session_id=interaction_logs.session_id)
    answer: str | None = None
    error_message: str | None = None
    evidences: list[InteractionEvidence] = []

    try:
        classifications = LLMSelectorService(
            api_key=runtime.api_key,
            model=runtime.settings.openai_model,
            usage_metrics=usage_metrics,
            interaction_logs=interaction_logs,
            entity_resolver=EntityResolutionService(),
        ).run(question, history[-HISTORY_MESSAGES_LIMIT:])

        ambiguous_classifications = [
            classification
            for classification in classifications
            if classification.status == "ambiguous"
        ]
        if ambiguous_classifications:
            # Adia todos os pedidos relevantes até as partes ambíguas serem esclarecidas.
            answer = "\n".join(
                clarification
                for classification in ambiguous_classifications
                if (clarification := classification.clarification_question)
            )
            interaction_logs.record(
                level="info",
                component=COMPONENT_INTERACTION,
                event="clarification_requested",
                message="Foi pedida uma clarificação ao utilizador.",
                details={"count": len(ambiguous_classifications)},
            )
        else:
            relevant_classifications = [
                classification
                for classification in classifications
                if classification.status == "relevant"
            ]
            if not relevant_classifications:
                answer = classifications[0].normalized_query
                interaction_logs.record(
                    level="info",
                    component=COMPONENT_INTERACTION,
                    event="out_of_scope_answer",
                    message="Foi devolvida a resposta para uma pergunta fora do âmbito.",
                )
            else:
                outcome = answer_relevant_questions(
                    classifications=relevant_classifications,
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
            component=COMPONENT_INTERACTION,
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
