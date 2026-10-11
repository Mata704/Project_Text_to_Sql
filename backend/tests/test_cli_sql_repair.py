from types import SimpleNamespace
from unittest.mock import Mock

from text_to_sql.errors import SQLiteDatabaseError
from text_to_sql.llms import LLMSQLRepairService
from text_to_sql.sql_execution import SQLExecutionWithRetriesService
from text_to_sql.sqlite_db import SQLiteService


def test_sql_execution_repair_stops_after_three_total_attempts(
    monkeypatch,
) -> None:
    sqlite_service = Mock(spec=SQLiteService)
    sqlite_service.fetch_all.side_effect = [
        SQLiteDatabaseError("first failure"),
        SQLiteDatabaseError("second failure"),
        SQLiteDatabaseError("third failure"),
    ]
    repair_service = Mock()
    repair_service.repair.side_effect = [
        SimpleNamespace(sql="SELECT 2", parameters=[]),
        SimpleNamespace(sql="SELECT 3", parameters=[]),
    ]

    monkeypatch.setattr(
        "text_to_sql.sql_execution.sql_execution_service.LLMSQLRepairService",
        lambda **_kwargs: repair_service,
    )

    result = SQLExecutionWithRetriesService(
        api_key="test-key",
        model="test-model",
        sqlite_service=sqlite_service,
    ).execute(question="Pergunta original", sql="SELECT 1", parameters={}, evidence=[])

    assert result.succeeded is False
    assert result.attempts == 3
    assert result.error == "third failure"
    assert sqlite_service.fetch_all.call_count == 3
    assert repair_service.repair.call_count == 2


def test_sql_execution_returns_results_after_one_repair(monkeypatch) -> None:
    sqlite_service = Mock(spec=SQLiteService)
    sqlite_service.fetch_all.side_effect = [
        SQLiteDatabaseError("first failure"),
        [{"total_viagens": 42}],
    ]

    repair_service = Mock(spec=LLMSQLRepairService)
    repair_service.repair.return_value = SimpleNamespace(
        sql="SELECT COUNT(*) FROM viagens",
        parameters=[],
    )
    monkeypatch.setattr(
        "text_to_sql.sql_execution.sql_execution_service.LLMSQLRepairService",
        lambda **_kwargs: repair_service,
    )

    result = SQLExecutionWithRetriesService(
        api_key="test-key",
        model="test-model",
        sqlite_service=sqlite_service,
    ).execute(
        question="Quantas viagens?",
        sql="SELECT COUNT(*) FROM viagens WHERE estado = 'x'",
        parameters={},
        evidence=[],
    )

    assert result.succeeded is True
    assert result.rows == [{"total_viagens": 42}]
    assert result.sql == "SELECT COUNT(*) FROM viagens"
    assert sqlite_service.fetch_all.call_count == 2
