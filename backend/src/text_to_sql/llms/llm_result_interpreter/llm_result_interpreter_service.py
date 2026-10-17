from collections.abc import Sequence

from text_to_sql.constants import COMPONENT_RESULT_INTERPRETER
from text_to_sql.llms.common import create_openai_client, parse_structured_response
from text_to_sql.llms.llm_result_interpreter.constants import (
    DEFAULT_RESULT_INTERPRETER_MODEL,
    RESULT_INTERPRETATION_INSTRUCTIONS,
)
from text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_model import (
    QuestionResult,
    ResultInterpretation,
)
from text_to_sql.usage_metrics import UsageMetricsService


class LLMResultInterpreterService:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_RESULT_INTERPRETER_MODEL,
        usage_metrics: UsageMetricsService | None = None,
    ) -> None:
        self.client = create_openai_client(api_key)
        self.model = model
        self.usage_metrics = usage_metrics

    def interpret(
        self,
        results: Sequence[QuestionResult],
    ) -> str:
        if not results:
            raise ValueError("At least one question result is required for interpretation.")

        response_input = (
            f"Perguntas relevantes e resultados das respetivas consultas:\n{list(results)!r}"
        )
        interpretation = parse_structured_response(
            self.client,
            model=self.model,
            instructions=RESULT_INTERPRETATION_INSTRUCTIONS,
            messages=[{"role": "user", "content": response_input}],
            response_model=ResultInterpretation,
            action="interpret SQL results",
            result_name="result interpretation",
            usage_metrics=self.usage_metrics,
            usage_component=COMPONENT_RESULT_INTERPRETER,
        )
        return interpretation.answer
