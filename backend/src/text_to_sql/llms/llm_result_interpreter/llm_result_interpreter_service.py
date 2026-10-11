from collections.abc import Sequence

from text_to_sql.llms.common import create_openai_client, parse_structured_response
from text_to_sql.llms.llm_result_interpreter.constants import (
    DEFAULT_RESULT_INTERPRETER_MODEL,
    RESULT_INTERPRETATION_INSTRUCTIONS,
)
from text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_model import (
    ResultInterpretation,
)


class LLMResultInterpreterService:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_RESULT_INTERPRETER_MODEL,
    ) -> None:
        self.client = create_openai_client(api_key)
        self.model = model

    def interpret(
        self,
        question: str,
        rows: Sequence[dict[str, object]],
    ) -> str:
        question = question.strip()
        if not question:
            raise ValueError("The result interpretation question cannot be empty.")

        response_input = (
            f"Pergunta original:\n{question}\n\n"
            f"Resultados obtidos pela execução SQL:\n{list(rows)!r}"
        )
        interpretation = parse_structured_response(
            self.client,
            model=self.model,
            instructions=RESULT_INTERPRETATION_INSTRUCTIONS,
            messages=[{"role": "user", "content": response_input}],
            response_model=ResultInterpretation,
            action="interpret SQL results",
            result_name="result interpretation",
        )
        return interpretation.answer
