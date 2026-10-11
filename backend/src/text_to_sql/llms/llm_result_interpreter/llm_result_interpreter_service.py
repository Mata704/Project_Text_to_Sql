from collections.abc import Sequence

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from text_to_sql.errors import LLMError
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
        try:
            self.client = OpenAI(api_key=api_key)
        except OpenAIError as error:
            raise LLMError(f"Could not initialize the OpenAI client: {error}") from error
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
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=RESULT_INTERPRETATION_INSTRUCTIONS,
                input=[{"role": "user", "content": response_input}],
                text_format=ResultInterpretation,
            )
        except OpenAIError as error:
            raise LLMError(f"OpenAI could not interpret SQL results: {error}") from error
        except ValidationError as error:
            raise LLMError(f"OpenAI returned an invalid result interpretation: {error}") from error

        if response.output_parsed is None:
            raise LLMError("OpenAI did not return a structured result interpretation.")
        try:
            interpretation = ResultInterpretation.model_validate(response.output_parsed)
        except ValidationError as error:
            raise LLMError(f"OpenAI returned an invalid result interpretation: {error}") from error
        return interpretation.answer
