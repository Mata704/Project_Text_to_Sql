from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from text_to_sql.errors import LLMError
from text_to_sql.llms import LLMSQLGeneratorService
from text_to_sql.llms.llm_sql_generator import SQLGenerationResult
from text_to_sql.retrieval import RetrievedChunk
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
    with patch(
        "text_to_sql.llms.llm_sql_generator.llm_sql_generator_service.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key", model="test-model")

    result = service.generate("Quantas viagens existem?", _evidence())

    assert result.sql == "SELECT COUNT(*) FROM viagens;"
    assert result.parameters == []
    assert result.citations[0].chunk_id == "schema-1"
    call = mock_client.responses.parse.call_args.kwargs
    assert call["model"] == "test-model"
    assert call["text_format"] is SQLGenerationResult
    assert "SELECT" in call["instructions"]
    assert "Quantas viagens existem?" in call["input"][0]["content"]
    assert "A tabela viagens contém a data_viagem." in call["input"][0]["content"]


def test_sql_generator_returns_abstention_without_evidence() -> None:
    mock_client = Mock()
    with patch(
        "text_to_sql.llms.llm_sql_generator.llm_sql_generator_service.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key")

    result = service.generate("Quantas viagens existem?", [])

    assert result.answerable is False
    assert result.sql is None
    assert result.citations == []
    mock_client.responses.parse.assert_not_called()


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
        "text_to_sql.llms.llm_sql_generator.llm_sql_generator_service.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key")

    with pytest.raises(LLMError, match="cited unknown evidence"):
        service.generate("Quantas viagens existem?", _evidence())


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
        "text_to_sql.llms.llm_sql_generator.llm_sql_generator_service.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLGeneratorService(api_key="test-key")

    with pytest.raises(LLMError, match="quote that is not present"):
        service.generate("Quantas viagens existem?", _evidence())
