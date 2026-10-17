from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from text_to_sql.errors import LLMError, SQLiteDatabaseError
from text_to_sql.interaction_logs import InteractionLogService
from text_to_sql.llms import LLMSQLGeneratorService
from text_to_sql.llms.common import OpenAIRequestError
from text_to_sql.llms.llm_sql_generator import SQLGenerationResult
from text_to_sql.retrieval import RetrievedChunk
from text_to_sql.sqlite_db import SQLiteService
from text_to_sql.vector_store import StoredChunk


def _evidence(content: str = "A tabela viagens contém a data_viagem.") -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk=StoredChunk(
                chunk_id="schema-1",
                content=content,
                metadata={"source": "01-schema.md"},
                distance=0.1,
            ),
            score=0.9,
        )
    ]


def _result() -> SQLGenerationResult:
    return SQLGenerationResult(
        answerable=True,
        sql="SELECT COUNT(*) FROM viagens;",
        explanation="Conta os registos da tabela viagens.",
        citations=[
            {
                "source": "01-schema.md",
                "chunk_id": "schema-1",
                "quote": "A tabela viagens contém a data_viagem.",
            }
        ],
    )


def test_sql_generator_returns_structured_sql_and_validates_citation() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(output_parsed=_result())
    sqlite_service = Mock(spec=SQLiteService)
    interaction_logs = InteractionLogService()
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(
            api_key="test-key",
            model="test-model",
            sqlite_service=sqlite_service,
            interaction_logs=interaction_logs,
        )

    result = service.generate("Quantas viagens existem?", _evidence())

    assert result.sql == "SELECT COUNT(*) FROM viagens;"
    assert result.parameters == []
    assert result.citations[0].chunk_id == "schema-1"
    call = mock_client.responses.parse.call_args.kwargs
    assert call["model"] == "test-model"
    assert call["text_format"] is SQLGenerationResult
    assert "SELECT" in call["instructions"]
    assert "COUNT para contagens" in call["instructions"]
    assert "SUM para totais" in call["instructions"]
    assert "AVG para médias" in call["instructions"]
    assert "MIN para mínimos" in call["instructions"]
    assert "MAX para máximos" in call["instructions"]
    assert "COUNT(DISTINCT coluna)" in call["instructions"]
    assert "denominador solicitado" in call["instructions"]
    assert "SUM(CASE WHEN condição THEN 1 ELSE 0 END)" in call["instructions"]
    assert "Taxas por grupo" in call["instructions"]
    assert "utiliza HAVING, e não WHERE" in call["instructions"]
    assert "Verifica o sinal da subtração" in call["instructions"]
    assert "Maior ou menor agregado por entidade" in call["instructions"]
    assert "entidade associada ao maior ou menor valor" in call["instructions"]
    assert "Quantas viagens existem?" in call["input"][0]["content"]
    assert "A tabela viagens contém a data_viagem." in call["input"][0]["content"]
    sqlite_service.validate_select.assert_called_once_with(
        "SELECT COUNT(*) FROM viagens;",
        {},
    )
    assert interaction_logs.entries[-1].event == "select_validated"
    assert interaction_logs.entries[-1].details == {
        "attempt": 1,
        "attempt_limit": 3,
        "question": "Quantas viagens existem?",
        "sql": "SELECT COUNT(*) FROM viagens;",
        "parameter_names": [],
        "citation_sources": ["01-schema.md"],
    }


def test_sql_generator_uses_same_failure_when_there_is_no_evidence() -> None:
    mock_client = Mock()
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key")

    with pytest.raises(LLMError, match="Não foi possível gerar uma query SQL segura"):
        service.generate("Quantas viagens existem?", [])
    mock_client.responses.parse.assert_not_called()


def test_sql_generator_does_not_retry_openai_request_failures() -> None:
    mock_client = Mock()
    mock_client.responses.parse.side_effect = OpenAIRequestError("request failed")
    with patch("text_to_sql.llms.common.OpenAI", return_value=mock_client):
        service = LLMSQLGeneratorService(api_key="test-key")

    with pytest.raises(OpenAIRequestError, match="request failed"):
        service.generate("Quantas viagens existem?", _evidence())

    mock_client.responses.parse.assert_called_once()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE viagens",
        "WITH dados AS (SELECT 1) SELECT * FROM dados",
        "SELECT 1; DROP TABLE viagens",
    ],
)
def test_sql_generation_result_rejects_non_select_queries(sql: str) -> None:
    with pytest.raises(ValidationError, match="read-only SELECT|exactly one statement"):
        SQLGenerationResult(
            answerable=True,
            sql=sql,
            explanation="Consulta.",
            citations=[
                {
                    "source": "01-schema.md",
                    "chunk_id": "schema-1",
                    "quote": "citação",
                }
            ],
        )


def test_sql_generator_rejects_non_select_response_from_model() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(
        output_parsed={
            "answerable": True,
            "sql": "DELETE FROM viagens",
            "parameters": [],
            "explanation": "Consulta.",
            "citations": [
                {
                    "source": "01-schema.md",
                    "chunk_id": "schema-1",
                    "quote": "citação",
                }
            ],
        }
    )
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key")

    with pytest.raises(LLMError, match="Não foi possível gerar uma query SQL segura"):
        service.generate("Quantas viagens existem?", _evidence())

    assert mock_client.responses.parse.call_count == 3


def test_sql_generator_rejects_invalid_sqlite_query() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(
        output_parsed={
            "answerable": True,
            "sql": "SELECT coluna_inexistente FROM viagens",
            "parameters": [],
            "explanation": "Consulta.",
            "citations": [
                {
                    "source": "01-schema.md",
                    "chunk_id": "schema-1",
                    "quote": "A tabela viagens contém a data_viagem.",
                }
            ],
        }
    )
    sqlite_service = Mock(spec=SQLiteService)
    sqlite_service.validate_select.side_effect = SQLiteDatabaseError(
        "Generated SQL is not a valid SELECT query: no such column"
    )
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(
            api_key="test-key",
            sqlite_service=sqlite_service,
        )

    with pytest.raises(
        LLMError,
        match="Não foi possível gerar uma query SQL segura.*no such column",
    ):
        service.generate("Quantas viagens existem?", _evidence())

    assert sqlite_service.validate_select.call_count == 3
    assert mock_client.responses.parse.call_count == 3


def test_sql_generator_retries_unsafe_query_and_returns_safe_replacement() -> None:
    mock_client = Mock()
    mock_client.responses.parse.side_effect = [
        Mock(
            output_parsed={
                "answerable": True,
                "sql": "DELETE FROM viagens",
                "parameters": [],
                "explanation": "Consulta.",
                "citations": [
                    {
                        "source": "01-schema.md",
                        "chunk_id": "schema-1",
                        "quote": "A tabela viagens contém a data_viagem.",
                    }
                ],
            }
        ),
        Mock(output_parsed=_result()),
    ]
    sqlite_service = Mock(spec=SQLiteService)
    interaction_logs = InteractionLogService()
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(
            api_key="test-key",
            sqlite_service=sqlite_service,
            interaction_logs=interaction_logs,
        )

    result = service.generate("Quantas viagens existem?", _evidence())

    assert result.sql == "SELECT COUNT(*) FROM viagens;"
    assert mock_client.responses.parse.call_count == 2
    assert (
        "nova resposta completa"
        in (mock_client.responses.parse.call_args_list[1].kwargs["input"][0]["content"])
    )
    sqlite_service.validate_select.assert_called_once_with(
        "SELECT COUNT(*) FROM viagens;",
        {},
    )
    rejected_attempt = interaction_logs.entries[-2]
    assert rejected_attempt.event == "generation_attempt_rejected"
    assert rejected_attempt.level == "debug"
    assert rejected_attempt.details["attempt"] == 1
    assert rejected_attempt.details["will_retry"] is True
    assert rejected_attempt.details["reason"]
    assert interaction_logs.entries[-1].event == "select_validated"
    assert interaction_logs.entries[-1].details == {
        "attempt": 2,
        "attempt_limit": 3,
        "question": "Quantas viagens existem?",
        "sql": "SELECT COUNT(*) FROM viagens;",
        "parameter_names": [],
        "citation_sources": ["01-schema.md"],
    }


def test_sql_generator_retries_unanswerable_response_and_returns_safe_query() -> None:
    mock_client = Mock()
    mock_client.responses.parse.side_effect = [
        Mock(
            output_parsed={
                "answerable": False,
                "sql": None,
                "parameters": [],
                "explanation": "A primeira resposta não tinha query.",
                "citations": [],
            }
        ),
        Mock(output_parsed=_result()),
    ]
    sqlite_service = Mock(spec=SQLiteService)
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(
            api_key="test-key",
            sqlite_service=sqlite_service,
        )

    result = service.generate("Quantas viagens existem?", _evidence())

    assert result.sql == "SELECT COUNT(*) FROM viagens;"
    assert mock_client.responses.parse.call_count == 2


def test_sql_generation_result_requires_parameters_for_named_placeholders() -> None:
    with pytest.raises(ValidationError, match="placeholders must exactly match"):
        SQLGenerationResult(
            answerable=True,
            sql="SELECT * FROM viagens WHERE data_viagem = :travel_date",
            explanation="Consulta por data.",
            citations=[
                {
                    "source": "01-schema.md",
                    "chunk_id": "schema-1",
                    "quote": "citação",
                }
            ],
        )


def test_sql_generation_result_accepts_named_parameters() -> None:
    result = SQLGenerationResult(
        answerable=True,
        sql="SELECT * FROM viagens WHERE data_viagem = :travel_date",
        parameters=[{"name": "travel_date", "value": "2026-10-05"}],
        explanation="Consulta por data.",
        citations=[
            {
                "source": "01-schema.md",
                "chunk_id": "schema-1",
                "quote": "citação",
            }
        ],
    )

    assert result.parameters[0].name == "travel_date"


def test_sql_generation_result_schema_uses_supported_parameter_array() -> None:
    schema = SQLGenerationResult.model_json_schema()
    properties = schema["properties"]
    parameter_item = properties["parameters"]["items"]
    if "$ref" in parameter_item:
        definition_name = parameter_item["$ref"].rsplit("/", maxsplit=1)[-1]
        parameter_item = schema["$defs"][definition_name]

    assert properties["parameters"]["type"] == "array"
    assert parameter_item["type"] == "object"
    assert parameter_item["additionalProperties"] is False


def test_sql_generator_rejects_unknown_citation() -> None:
    generated = SQLGenerationResult(
        answerable=True,
        sql="SELECT COUNT(*) FROM viagens",
        explanation="Conta viagens.",
        citations=[
            {
                "source": "missing.md",
                "chunk_id": "unknown",
                "quote": "citação",
            }
        ],
    )
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(output_parsed=generated)
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key")

    with pytest.raises(LLMError, match="Não foi possível gerar uma query SQL segura"):
        service.generate("Quantas viagens existem?", _evidence())
    assert mock_client.responses.parse.call_count == 3


def test_sql_generator_rejects_quote_not_present_in_cited_chunk() -> None:
    generated = SQLGenerationResult(
        answerable=True,
        sql="SELECT COUNT(*) FROM viagens",
        explanation="Conta viagens.",
        citations=[
            {
                "source": "01-schema.md",
                "chunk_id": "schema-1",
                "quote": "Texto inexistente.",
            }
        ],
    )
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(output_parsed=generated)
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key")

    with pytest.raises(LLMError, match="Não foi possível gerar uma query SQL segura"):
        service.generate("Quantas viagens existem?", _evidence())
    assert mock_client.responses.parse.call_count == 3


def test_sql_generator_maps_inexact_quote_to_closest_chunk_line() -> None:
    generated = SQLGenerationResult(
        answerable=True,
        sql="SELECT COUNT(*) FROM viagens",
        explanation="Conta viagens.",
        citations=[
            {
                "source": "01-schema.md",
                "chunk_id": "schema-1",
                "quote": "`viagens`: comboio, data, origem e destino",
            }
        ],
    )
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(output_parsed=generated)
    with patch("text_to_sql.llms.common.OpenAI", return_value=mock_client):
        service = LLMSQLGeneratorService(api_key="test-key")

    content = (
        "Tabelas:\n- `viagens`: comboio, data, origem, destino e estado.\n- `estacoes`: nomes."
    )
    result = service.generate("Quantas viagens existem?", _evidence(content))

    assert result.citations[0].quote == "- `viagens`: comboio, data, origem, destino e estado."
    assert mock_client.responses.parse.call_count == 1
