from collections.abc import Sequence

from text_to_sql.errors import SQLiteDatabaseError
from text_to_sql.llms import LLMSQLRepairService
from text_to_sql.retrieval import RetrievedChunk
from text_to_sql.sql_execution.sql_execution_model import (
    SQLExecutionResult,
    SQLiteValue,
)
from text_to_sql.sqlite_db import SQLiteService
from text_to_sql.usage_metrics import UsageMetricsService

MAX_SQL_EXECUTIONS = 3


class SQLExecutionWithRetriesService:
    def __init__(
        self,
        api_key: str,
        model: str,
        sqlite_service: SQLiteService | None = None,
        usage_metrics: UsageMetricsService | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.sqlite_service = sqlite_service or SQLiteService()
        self.usage_metrics = usage_metrics

    def execute(
        self,
        question: str,
        sql: str,
        parameters: dict[str, SQLiteValue],
        evidence: Sequence[RetrievedChunk],
    ) -> SQLExecutionResult:
        current_sql = sql
        current_parameters = parameters
        for attempt in range(1, MAX_SQL_EXECUTIONS + 1):
            try:
                rows = self.sqlite_service.fetch_all(current_sql, current_parameters)
            except SQLiteDatabaseError as error:
                if attempt == MAX_SQL_EXECUTIONS:
                    return SQLExecutionResult(
                        succeeded=False,
                        sql=current_sql,
                        parameters=current_parameters,
                        attempts=attempt,
                    )

                repair = LLMSQLRepairService(
                    api_key=self.api_key,
                    model=self.model,
                    sqlite_service=self.sqlite_service,
                    usage_metrics=self.usage_metrics,
                ).repair(
                    question=question,
                    sql=current_sql,
                    parameters=current_parameters,
                    error=str(error),
                    evidence=evidence,
                )
                current_sql = repair.sql
                current_parameters = {
                    parameter.name: parameter.value for parameter in repair.parameters
                }
            else:
                return SQLExecutionResult(
                    succeeded=True,
                    sql=current_sql,
                    parameters=current_parameters,
                    rows=rows,
                    attempts=attempt,
                )

        raise RuntimeError("SQL execution attempt loop ended unexpectedly.")
