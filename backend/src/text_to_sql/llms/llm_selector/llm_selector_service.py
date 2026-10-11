from collections.abc import Sequence
from uuid import uuid4

from openai.types.responses import EasyInputMessageParam, ResponseInputItemParam

from text_to_sql.llms.common import create_openai_client, parse_structured_response
from text_to_sql.llms.llm_selector.constants import (
    CLASSIFICATION_INSTRUCTIONS,
    MAX_CLARIFICATION_ITERATIONS,
    PROMPT_INJECTION_TERMS_PATTERN,
)
from text_to_sql.llms.llm_selector.llm_selector_model import (
    ConversationMessage,
    QuestionClassificationResult,
)
from text_to_sql.usage_metrics import UsageMetricsService


def _response_input_message(message: ConversationMessage) -> ResponseInputItemParam:
    return EasyInputMessageParam(role=message.role, content=message.content)


class _ConversationContext:
    def __init__(self) -> None:
        self.session_id = str(uuid4())
        self._messages: list[ConversationMessage] = []

    @property
    def messages(self) -> list[ConversationMessage]:
        return list(self._messages)

    def add_clarification_exchange(self, question: str, clarification: str) -> None:
        self._messages.extend(
            [
                ConversationMessage(role="user", content=question),
                ConversationMessage(role="assistant", content=clarification),
            ]
        )
        self._messages = self._messages[-2 * MAX_CLARIFICATION_ITERATIONS :]


class LLMSelectorService:
    def __init__(
        self,
        api_key: str,
        model: str,
        usage_metrics: UsageMetricsService | None = None,
    ) -> None:
        self.client = create_openai_client(api_key)
        self.model = model
        self.usage_metrics = usage_metrics

    def run(self, question: str) -> QuestionClassificationResult:
        question = question.strip()
        if not question:
            raise ValueError("The question cannot be empty.")

        context = _ConversationContext()
        for iteration in range(MAX_CLARIFICATION_ITERATIONS):
            classification = self.classify_question(question, context.messages)
            print("Resposta da primeira LLM:")
            print(classification.model_dump_json(indent=2))

            if classification.status in {"relevant", "irrelevant"}:
                return classification

            if iteration == MAX_CLARIFICATION_ITERATIONS - 1:
                print(
                    "Não foi possível clarificar a pergunta no limite de "
                    f"{MAX_CLARIFICATION_ITERATIONS} iterações."
                )
                return classification

            clarification = classification.clarification_question
            print(f"Clarificação necessária: {clarification}")
            context.add_clarification_exchange(question, clarification or "")
            question = input("Resposta: ").strip()
            if not question:
                raise ValueError("The clarification answer cannot be empty.")

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
