from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from text_to_sql.errors import LLMError, SQLiteDatabaseError
from text_to_sql.llms import LLMSQLRepairService
from text_to_sql.llms.llm_sql_repair import SQLRepairResult
from text_to_sql.sqlite_db import SQLiteService


def _response(sql: str = "SELECT 1") -> Mock:
    return Mock(
        output_parsed={
            "sql": sql,
            "parameters": [],
        }
    )


def test_sql_repair_returns_select_and_validates_it_with_sqlite() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = _response()
    sqlite_service = Mock(spec=SQLiteService)
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLRepairService(
            api_key="test-key",
            model="test-model",
            sqlite_service=sqlite_service,
        )

    result = service.repair(
        question="Quantas viagens existem?",
        sql="SELECT coluna_errada FROM viagens",
        parameters={},
        error="no such column: coluna_errada",
        evidence=[],
    )

    assert result.sql == "SELECT 1"
    sqlite_service.validate_select.assert_called_once_with("SELECT 1", {})
    call = mock_client.responses.parse.call_args.kwargs
    assert call["model"] == "test-model"
    assert call["text_format"] is SQLRepairResult
    assert "no such column: coluna_errada" in call["input"][0]["content"]


@pytest.mark.parametrize(
    "sql",
    ["DELETE FROM viagens", "WITH dados AS (SELECT 1) SELECT * FROM dados"],
)
def test_sql_repair_rejects_non_select_queries(sql: str) -> None:
    with pytest.raises(ValidationError):
        SQLRepairResult(sql=sql)


def test_sql_repair_rejects_query_not_accepted_by_sqlite() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = _response("SELECT coluna_inexistente FROM viagens")
    sqlite_service = Mock(spec=SQLiteService)
    sqlite_service.validate_select.side_effect = SQLiteDatabaseError(
        "Generated SQL is not a valid SELECT query: no such column"
    )
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMSQLRepairService(
            api_key="test-key",
            sqlite_service=sqlite_service,
        )

    with pytest.raises(LLMError, match="invalid SQL repair"):
        service.repair("Pergunta?", "SELECT 1", {}, "erro", [])


def test_sql_repair_requires_matching_named_parameters() -> None:
    with pytest.raises(ValidationError, match="placeholders"):
        SQLRepairResult(
            sql="SELECT * FROM viagens WHERE id_viagem = :travel_id",
            parameters=[],
        )
