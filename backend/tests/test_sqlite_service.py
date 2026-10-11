from pathlib import Path

import pytest

from text_to_sql.errors import SQLiteDatabaseError
from text_to_sql.sample_database import SampleDatabaseService
from text_to_sql.sqlite_db import SQLiteConfig, SQLiteService


@pytest.fixture
def sqlite_service(tmp_path: Path) -> SQLiteService:
    database_path = tmp_path / "comboios.sqlite3"
    config = SQLiteConfig(database_path=database_path)
    SampleDatabaseService(database_path).ensure_current()
    return SQLiteService(config)


def test_fetch_all_and_fetch_one_support_parameterized_queries(
    sqlite_service: SQLiteService,
) -> None:
    stations = sqlite_service.fetch_all(
        "SELECT nome, cidade FROM estacoes WHERE cidade = ? ORDER BY id_estacao",
        ("Lisboa",),
    )
    station = sqlite_service.fetch_one(
        "SELECT nome FROM estacoes WHERE id_estacao = :station_id",
        {"station_id": 1},
    )

    assert stations == [
        {"nome": "Lisboa - Santa Apolónia", "cidade": "Lisboa"},
        {"nome": "Lisboa - Oriente", "cidade": "Lisboa"},
    ]
    assert station == {"nome": "Lisboa - Santa Apolónia"}
    assert (
        sqlite_service.fetch_one(
            "SELECT nome FROM estacoes WHERE nome = ?",
            ("missing station",),
        )
        is None
    )


def test_fetch_queries_are_read_only_and_parameters_are_not_sql(
    sqlite_service: SQLiteService,
) -> None:
    injected_value = "' OR 1=1 --"

    assert (
        sqlite_service.fetch_all(
            "SELECT nome FROM estacoes WHERE nome = ?",
            (injected_value,),
        )
        == []
    )
    with pytest.raises(SQLiteDatabaseError, match="Could not read from SQLite"):
        sqlite_service.fetch_all("DELETE FROM estacoes")


def test_validate_select_checks_sql_schema_and_parameters(sqlite_service: SQLiteService) -> None:
    sqlite_service.validate_select(
        "SELECT nome FROM estacoes WHERE cidade = :city",
        {"city": "Lisboa"},
    )

    with pytest.raises(SQLiteDatabaseError, match="not a valid SELECT query"):
        sqlite_service.validate_select("SELECT coluna_inexistente FROM estacoes")


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM estacoes",
        "SELECT nome FROM estacoes; DELETE FROM estacoes",
    ],
)
def test_validate_select_rejects_non_select_or_multiple_statements(
    sqlite_service: SQLiteService,
    query: str,
) -> None:
    with pytest.raises(SQLiteDatabaseError):
        sqlite_service.validate_select(query)


def test_execute_commits_writes_and_returns_row_metadata(
    sqlite_service: SQLiteService,
) -> None:
    insert_result = sqlite_service.execute(
        """
        INSERT INTO comboios (codigo, tipo, operador, capacidade)
        VALUES (?, ?, ?, ?)
        """,
        ("TEST1", "Regional", "Comboios Pedro Mata", 100),
    )
    update_result = sqlite_service.execute(
        "UPDATE comboios SET capacidade = ? WHERE id_comboio = ?",
        (120, insert_result.last_row_id),
    )

    assert insert_result.row_count == 1
    assert insert_result.last_row_id is not None
    assert update_result.row_count == 1
    assert sqlite_service.fetch_one(
        "SELECT capacidade FROM comboios WHERE id_comboio = ?",
        (insert_result.last_row_id,),
    ) == {"capacidade": 120}


def test_execute_many_is_atomic(sqlite_service: SQLiteService) -> None:
    count_before = sqlite_service.fetch_one("SELECT COUNT(*) AS count FROM comboios")

    with pytest.raises(SQLiteDatabaseError, match="Could not write to SQLite"):
        sqlite_service.execute_many(
            """
            INSERT INTO comboios (codigo, tipo, operador, capacidade)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("TEST1", "Regional", "Comboios Pedro Mata", 100),
                ("IC523", "Regional", "Comboios Pedro Mata", 100),
            ],
        )

    assert sqlite_service.fetch_one("SELECT COUNT(*) AS count FROM comboios") == count_before


def test_service_reports_missing_database_and_empty_queries(tmp_path: Path) -> None:
    service = SQLiteService(SQLiteConfig(database_path=tmp_path / "missing.sqlite3"))

    with pytest.raises(SQLiteDatabaseError, match="database does not exist"):
        service.fetch_all("SELECT 1")
    with pytest.raises(ValueError, match="query cannot be empty"):
        service.execute(" ")
