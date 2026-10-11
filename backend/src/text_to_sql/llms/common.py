from collections.abc import Sequence
from time import perf_counter

from openai import OpenAI, OpenAIError
from openai.types.responses import ResponseInputItemParam
from pydantic import BaseModel, ValidationError

from text_to_sql.errors import LLMError
from text_to_sql.usage_metrics import UsageMetricsService


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
    usage_metrics: UsageMetricsService | None = None,
    usage_component: str = "llm",
) -> StructuredResult:
    started_at = perf_counter()
    try:
        response = client.responses.parse(
            model=model,
            instructions=instructions,
            input=messages,
            text_format=response_model,
        )
    except OpenAIError as error:
        if usage_metrics is not None:
            usage_metrics.record_call(
                component=usage_component,
                model=model,
                usage=None,
                elapsed_seconds=perf_counter() - started_at,
                succeeded=False,
            )
        raise OpenAIRequestError(f"OpenAI could not {action}: {error}") from error
    except ValidationError as error:
        if usage_metrics is not None:
            usage_metrics.record_call(
                component=usage_component,
                model=model,
                usage=None,
                elapsed_seconds=perf_counter() - started_at,
                succeeded=False,
            )
        raise LLMError(f"OpenAI returned an invalid {result_name}: {error}") from error

    if usage_metrics is not None:
        usage_metrics.record_call(
            component=usage_component,
            model=response.model or model,
            usage=response.usage,
            elapsed_seconds=perf_counter() - started_at,
        )

    if response.output_parsed is None:
        raise LLMError(f"OpenAI did not return a structured {result_name}.")
    try:
        return response_model.model_validate(response.output_parsed)
    except ValidationError as error:
        raise LLMError(f"OpenAI returned an invalid {result_name}: {error}") from error
