from collections.abc import Sequence
from typing import Literal

from openai.types.responses import EasyInputMessageParam, ResponseInputItemParam

from text_to_sql.constants import COMPONENT_ENTITY_RESOLUTION, COMPONENT_QUESTION_CLASSIFIER
from text_to_sql.entity_resolution import EntityResolutionService
from text_to_sql.errors import TextToSQLError
from text_to_sql.interaction_logs import InteractionLogService
from text_to_sql.interaction_logs.interaction_log_service import InteractionLogValue
from text_to_sql.llms.common import create_openai_client, parse_structured_response
from text_to_sql.llms.llm_selector.constants import (
    CLASSIFICATION_INSTRUCTIONS,
    PROMPT_INJECTION_TERMS_PATTERN,
)
from text_to_sql.llms.llm_selector.llm_selector_model import (
    ConversationMessage,
    QuestionClassificationResult,
    QuestionClassificationResults,
)
from text_to_sql.usage_metrics import UsageMetricsService


def _response_input_message(message: ConversationMessage) -> ResponseInputItemParam:
    return EasyInputMessageParam(role=message.role, content=message.content)


class LLMSelectorService:
    def __init__(
        self,
        api_key: str,
        model: str,
        usage_metrics: UsageMetricsService | None = None,
        interaction_logs: InteractionLogService | None = None,
        entity_resolver: EntityResolutionService | None = None,
    ) -> None:
        self.client = create_openai_client(api_key)
        self.model = model
        self.entity_resolver = entity_resolver
        self.usage_metrics = usage_metrics
        self.interaction_logs = interaction_logs

    def run(
        self,
        question: str,
        history: Sequence[ConversationMessage] = (),
    ) -> list[QuestionClassificationResult]:
        question = question.strip()
        if not question:
            raise ValueError("The question cannot be empty.")

        classifications = self.classify_question(question, history)
        if self.interaction_logs is not None:
            for classification in classifications:
                self.interaction_logs.record(
                    level="info",
                    component=COMPONENT_QUESTION_CLASSIFIER,
                    event="question_classified",
                    message="Uma pergunta foi classificada.",
                    details={
                        "question": question,
                        "status": classification.status,
                        "normalized_query": classification.normalized_query,
                        "clarification_question": classification.clarification_question,
                    },
                )
                if classification.status == "ambiguous":
                    self.interaction_logs.record(
                        level="warning",
                        component=COMPONENT_QUESTION_CLASSIFIER,
                        event="clarification_unresolved",
                        message="Uma pergunta requer clarificação do utilizador.",
                    )
        return classifications

    def classify_question(
        self,
        question: str,
        history: Sequence[ConversationMessage] = (),
    ) -> list[QuestionClassificationResult]:
        sanitized_question = self._sanitize_user_content(question)
        messages = [
            _response_input_message(
                ConversationMessage(
                    role=message.role,
                    content=self._sanitize_user_content(message.content),
                )
            )
            for message in history
            if PROMPT_INJECTION_TERMS_PATTERN.sub("", message.content).strip()
        ]
        messages.append(
            _response_input_message(ConversationMessage(role="user", content=sanitized_question))
        )

        result = parse_structured_response(
            self.client,
            model=self.model,
            instructions=self._instructions_with_entity_hints(sanitized_question),
            messages=messages,
            response_model=QuestionClassificationResults,
            action="classify the question",
            result_name="question classification",
            usage_metrics=self.usage_metrics,
            usage_component=COMPONENT_QUESTION_CLASSIFIER,
        )
        return self._deduplicate(result.classifications)

    def _instructions_with_entity_hints(self, question: str) -> str:
        if self.entity_resolver is None:
            return CLASSIFICATION_INSTRUCTIONS
        try:
            resolution = self.entity_resolver.run(question)
        except TextToSQLError as error:
            # Sem verificação de nomes o seletor continua a funcionar.
            self._record_entity_resolution(
                level="warning",
                event="entity_resolution_failed",
                message="A verificação de nomes falhou; o seletor segue sem ela.",
                details={"question": question, "error": str(error)},
            )
            return CLASSIFICATION_INSTRUCTIONS

        hints = resolution.to_prompt_hints()
        self._record_entity_resolution(
            level="info" if not resolution.suggestions else "warning",
            event="entities_resolved" if hints else "no_entity_changes",
            message=(
                "Foram encontrados nomes a corrigir ou confirmar."
                if hints
                else "Não foram encontrados nomes a corrigir."
            ),
            details={
                "question": question,
                "entities": [
                    {
                        "original": entity.original,
                        "canonical": entity.canonical,
                        "kind": entity.kind,
                        "columns": list(entity.columns),
                        "stations": list(entity.stations),
                        "score": entity.score,
                    }
                    for entity in resolution.entities
                ],
                "suggestions": [
                    {"original": item.original, "candidates": list(item.candidates)}
                    for item in resolution.suggestions
                ],
                "hints": hints,
            },
        )
        if not hints:
            return CLASSIFICATION_INSTRUCTIONS
        return f"{CLASSIFICATION_INSTRUCTIONS}\n\n{hints}"

    def _record_entity_resolution(
        self,
        *,
        level: Literal["debug", "info", "warning", "error"],
        event: str,
        message: str,
        details: dict[str, InteractionLogValue],
    ) -> None:
        if self.interaction_logs is not None:
            self.interaction_logs.record(
                level=level,
                component=COMPONENT_ENTITY_RESOLUTION,
                event=event,
                message=message,
                details=details,
            )

    @staticmethod
    def _deduplicate(
        classifications: Sequence[QuestionClassificationResult],
    ) -> list[QuestionClassificationResult]:
        unique: list[QuestionClassificationResult] = []
        seen: set[tuple[str, str]] = set()
        for classification in classifications:
            key = (
                classification.status,
                " ".join(classification.normalized_query.lower().split()),
            )
            if key not in seen:
                seen.add(key)
                unique.append(classification)
        return unique

    def _sanitize_user_content(self, content: str) -> str:
        sanitized = PROMPT_INJECTION_TERMS_PATTERN.sub("", content)
        sanitized = " ".join(sanitized.split()).strip()
        if not sanitized:
            raise ValueError("The question cannot be empty after removing unsafe prompt terms.")
        return sanitized
