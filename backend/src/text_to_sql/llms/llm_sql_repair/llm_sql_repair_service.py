from collections.abc import Sequence

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from text_to_sql.errors import LLMError, SQLiteDatabaseError
from text_to_sql.llms.llm_sql_repair.constants import (
    DEFAULT_SQL_REPAIR_MODEL,
    SQL_REPAIR_INSTRUCTIONS,
)
from text_to_sql.llms.llm_sql_repair.llm_sql_repair_model import SQLRepairResult
from text_to_sql.retrieval.retrieval_model import RetrievedChunk
from text_to_sql.sqlite_db import SQLiteService


class LLMSQLRepairService:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_SQL_REPAIR_MODEL,
        sqlite_service: SQLiteService | None = None,
    ) -> None:
        try:
            self.client = OpenAI(api_key=api_key)
        except OpenAIError as error:
            raise LLMError(f"Could not initialize the OpenAI client: {error}") from error
        self.model = model
        self.sqlite_service = sqlite_service or SQLiteService()

    def repair(
        self,
        question: str,
        sql: str,
        parameters: dict[str, str | int | float | None],
        error: str,
        evidence: Sequence[RetrievedChunk],
    ) -> SQLRepairResult:
        response_input = (
            f"Pergunta original:\n{question}\n\n"
            f"Query que falhou:\n{sql}\n\n"
            f"Parâmetros usados:\n{parameters}\n\n"
            f"Erro SQLite:\n{error}\n\n"
            f"Evidências disponíveis:\n{self._format_evidence(evidence)}"
        )
        try:
            response = self.client.responses.parse(
                model=self.model,
                instructions=SQL_REPAIR_INSTRUCTIONS,
                input=[{"role": "user", "content": response_input}],
                text_format=SQLRepairResult,
            )
        except OpenAIError as error:
            raise LLMError(f"OpenAI could not repair SQL: {error}") from error
        except ValidationError as error:
            raise LLMError(f"OpenAI returned an invalid SQL repair: {error}") from error

        if response.output_parsed is None:
            raise LLMError("OpenAI did not return a structured SQL repair.")
        try:
            result = SQLRepairResult.model_validate(response.output_parsed)
        except ValidationError as error:
            raise LLMError(f"OpenAI returned an invalid SQL repair: {error}") from error

        values = {parameter.name: parameter.value for parameter in result.parameters}
        try:
            self.sqlite_service.validate_select(result.sql, values)
        except SQLiteDatabaseError as error:
            raise LLMError(f"OpenAI returned an invalid SQL repair: {error}") from error
        return result

    def _format_evidence(self, evidence: Sequence[RetrievedChunk]) -> str:
        return "\n\n".join(
            f"[source={item.chunk.metadata.get('source', 'unknown')}; "
            f"chunk_id={item.chunk.chunk_id}]\n{item.chunk.content}"
            for item in evidence
        )
