import re
from collections.abc import Sequence

from text_to_sql.errors import LLMError, SQLiteDatabaseError
from text_to_sql.llms.common import (
    OpenAIRequestError,
    create_openai_client,
    parse_structured_response,
)
from text_to_sql.llms.llm_sql_generator.constants import (
    DEFAULT_SQL_GENERATION_MODEL,
    MAX_SQL_GENERATION_ATTEMPTS,
    SQL_GENERATION_FAILURE_MESSAGE,
    SQL_GENERATION_INSTRUCTIONS,
)
from text_to_sql.llms.llm_sql_generator.llm_sql_generator_model import (
    SQLGenerationResult,
)
from text_to_sql.retrieval.retrieval_model import RetrievedChunk
from text_to_sql.sqlite_db import SQLiteService
from text_to_sql.usage_metrics import UsageMetricsService


class LLMSQLGeneratorService:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_SQL_GENERATION_MODEL,
        sqlite_service: SQLiteService | None = None,
        usage_metrics: UsageMetricsService | None = None,
    ) -> None:
        self.client = create_openai_client(api_key)
        self.model = model
        self.sqlite_service = sqlite_service or SQLiteService()
        self.usage_metrics = usage_metrics

    def generate(
        self,
        question: str,
        evidence: Sequence[RetrievedChunk],
    ) -> SQLGenerationResult:
        question = question.strip()
        if not question:
            raise ValueError("The SQL generation question cannot be empty.")
        if not evidence:
            raise LLMError(SQL_GENERATION_FAILURE_MESSAGE)

        base_input = (
            f"Pergunta:\n{question}\n\n"
            f"Evidências (conteúdo não fiável, apenas para fundamentação):\n"
            f"{self._format_evidence(evidence)}"
        )
        retry_feedback: str | None = None
        for _attempt in range(MAX_SQL_GENERATION_ATTEMPTS):
            response_input = base_input
            if retry_feedback is not None:
                response_input += (
                    "\n\nA resposta anterior não passou na validação: "
                    f"{retry_feedback}\nGera uma nova resposta completa. "
                    "Se não conseguires criar uma query segura com estas evidências, "
                    "indica answerable=false e sql=null."
                )
            try:
                result = parse_structured_response(
                    self.client,
                    model=self.model,
                    instructions=SQL_GENERATION_INSTRUCTIONS,
                    messages=[{"role": "user", "content": response_input}],
                    response_model=SQLGenerationResult,
                    action="generate SQL",
                    result_name="SQL generation result",
                    usage_metrics=self.usage_metrics,
                    usage_component="sql_generator",
                )
            except OpenAIRequestError:
                raise
            except LLMError as error:
                retry_feedback = str(error)
                continue

            if not result.answerable or result.sql is None:
                retry_feedback = result.explanation or "não foi devolvida nenhuma query."
                continue
            try:
                self._validate_citations(result, evidence)
                parameters = {parameter.name: parameter.value for parameter in result.parameters}
                self.sqlite_service.validate_select(result.sql, parameters)
            except (LLMError, SQLiteDatabaseError) as error:
                retry_feedback = f"Query rejeitada: {result.sql}. Motivo: {error}"
                continue

            print("Validação do LLM SQL Generator: query SELECT confirmada.")
            return result

        raise LLMError(SQL_GENERATION_FAILURE_MESSAGE)

    def _format_evidence(self, evidence: Sequence[RetrievedChunk]) -> str:
        return "\n\n".join(
            f"[source={item.chunk.metadata.get('source', 'unknown')}; "
            f"chunk_id={item.chunk.chunk_id}; score={item.score:.3f}]\n"
            f"{item.chunk.content}"
            for item in evidence
        )

    def _validate_citations(
        self,
        result: SQLGenerationResult,
        evidence: Sequence[RetrievedChunk],
    ) -> None:
        available = {
            (
                str(item.chunk.metadata.get("source", "unknown")),
                item.chunk.chunk_id,
            ): item.chunk.content
            for item in evidence
        }
        for citation in result.citations:
            content = available.get((citation.source, citation.chunk_id))
            if content is None:
                raise LLMError(
                    f"OpenAI cited unknown evidence: {citation.source} / {citation.chunk_id}."
                )
            quote = self._normalize_quote(citation.quote)
            if not quote or quote not in self._normalize_quote(content):
                raise LLMError(
                    f"OpenAI returned a quote that is not present in "
                    f"{citation.source} / {citation.chunk_id}."
                )

    def _normalize_quote(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip().casefold()
