from collections.abc import Sequence

from openai import OpenAI, OpenAIError
from openai.types.responses import ResponseInputItemParam
from pydantic import BaseModel, ValidationError

from text_to_sql.errors import LLMError


class OpenAIRequestError(LLMError):
    """Raised when the OpenAI request itself fails."""


def create_openai_client(api_key: str) -> OpenAI:
    try:
        return OpenAI(api_key=api_key)
    except OpenAIError as error:
        raise LLMError(f"Could not initialize the OpenAI client: {error}") from error


def parse_structured_response[StructuredResult: BaseModel](
    client: OpenAI,
    *,
    model: str,
    instructions: str,
    messages: Sequence[ResponseInputItemParam],
    response_model: type[StructuredResult],
    action: str,
    result_name: str,
) -> StructuredResult:
    try:
        response = client.responses.parse(
            model=model,
            instructions=instructions,
            input=messages,
            text_format=response_model,
        )
    except OpenAIError as error:
        raise OpenAIRequestError(f"OpenAI could not {action}: {error}") from error
    except ValidationError as error:
        raise LLMError(f"OpenAI returned an invalid {result_name}: {error}") from error

    if response.output_parsed is None:
        raise LLMError(f"OpenAI did not return a structured {result_name}.")
    try:
        return response_model.model_validate(response.output_parsed)
    except ValidationError as error:
        raise LLMError(f"OpenAI returned an invalid {result_name}: {error}") from error
