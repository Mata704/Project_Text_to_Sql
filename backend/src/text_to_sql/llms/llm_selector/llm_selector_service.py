from collections.abc import Sequence

from openai.types.responses import EasyInputMessageParam, ResponseInputItemParam

from text_to_sql.interaction_logs import InteractionLogService
from text_to_sql.llms.common import create_openai_client, parse_structured_response
from text_to_sql.llms.llm_selector.constants import (
    CLASSIFICATION_INSTRUCTIONS,
    PROMPT_INJECTION_TERMS_PATTERN,
)
from text_to_sql.llms.llm_selector.llm_selector_model import (
    ConversationMessage,
    QuestionClassificationResult,
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
    ) -> None:
        self.client = create_openai_client(api_key)
        self.model = model
        self.usage_metrics = usage_metrics
        self.interaction_logs = interaction_logs

    def run(self, question: str) -> QuestionClassificationResult:
        question = question.strip()
        if not question:
            raise ValueError("The question cannot be empty.")

        classification = self.classify_question(question)
        if self.interaction_logs is not None:
            self.interaction_logs.record(
                level="info",
                component="question_classifier",
                event="question_classified",
                message="A pergunta foi classificada.",
                details={"status": classification.status},
            )
            if classification.status == "ambiguous":
                self.interaction_logs.record(
                    level="warning",
                    component="question_classifier",
                    event="clarification_unresolved",
                    message="A pergunta requer clarificação do utilizador.",
                )
        return classification

    def classify_question(
        self,
        question: str,
        history: Sequence[ConversationMessage] = (),
    ) -> QuestionClassificationResult:
        sanitized_question = self._sanitize_user_content(question)
        messages = [
            _response_input_message(
                ConversationMessage(
                    role=message.role,
                    content=self._sanitize_user_content(message.content),
                )
            )
            for message in history
        ]
        messages.append(
            _response_input_message(ConversationMessage(role="user", content=sanitized_question))
        )

        return parse_structured_response(
            self.client,
            model=self.model,
            instructions=CLASSIFICATION_INSTRUCTIONS,
            messages=messages,
            response_model=QuestionClassificationResult,
            action="classify the question",
            result_name="question classification",
            usage_metrics=self.usage_metrics,
            usage_component="question_classifier",
        )

    def _sanitize_user_content(self, content: str) -> str:
        sanitized = PROMPT_INJECTION_TERMS_PATTERN.sub("", content)
        sanitized = " ".join(sanitized.split()).strip()
        if not sanitized:
            raise ValueError("The question cannot be empty after removing unsafe prompt terms.")
        return sanitized
