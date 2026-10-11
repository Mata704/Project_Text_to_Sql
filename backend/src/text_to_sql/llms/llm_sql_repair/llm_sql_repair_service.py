from collections.abc import Sequence

from text_to_sql.constants import COMPONENT_SQL_REPAIR, UNKNOWN_SOURCE
from text_to_sql.errors import LLMError, SQLiteDatabaseError
from text_to_sql.llms.common import create_openai_client, parse_structured_response
from text_to_sql.llms.llm_sql_repair.constants import (
    DEFAULT_SQL_REPAIR_MODEL,
    SQL_REPAIR_INSTRUCTIONS,
)
from text_to_sql.llms.llm_sql_repair.llm_sql_repair_model import SQLRepairResult
from text_to_sql.retrieval.retrieval_model import RetrievedChunk
from text_to_sql.sqlite_db import SQLiteService
from text_to_sql.usage_metrics import UsageMetricsService


class LLMSQLRepairService:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_SQL_REPAIR_MODEL,
        sqlite_service: SQLiteService | None = None,
        usage_metrics: UsageMetricsService | None = None,
    ) -> None:
        self.client = create_openai_client(api_key)
        self.model = model
        self.sqlite_service = sqlite_service or SQLiteService()
        self.usage_metrics = usage_metrics

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
        result = parse_structured_response(
            self.client,
            model=self.model,
            instructions=SQL_REPAIR_INSTRUCTIONS,
            messages=[{"role": "user", "content": response_input}],
            response_model=SQLRepairResult,
            action="repair SQL",
            result_name="SQL repair",
            usage_metrics=self.usage_metrics,
            usage_component=COMPONENT_SQL_REPAIR,
        )

        values = {parameter.name: parameter.value for parameter in result.parameters}
        try:
            self.sqlite_service.validate_select(result.sql, values)
        except SQLiteDatabaseError as error:
            raise LLMError(f"OpenAI returned an invalid SQL repair: {error}") from error
        return result

    def _format_evidence(self, evidence: Sequence[RetrievedChunk]) -> str:
        return "\n\n".join(
            f"[source={item.chunk.metadata.get('source', UNKNOWN_SOURCE)}; "
            f"chunk_id={item.chunk.chunk_id}]\n{item.chunk.content}"
            for item in evidence
        )
