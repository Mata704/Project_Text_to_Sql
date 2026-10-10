import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from text_to_sql.sample_database import SampleDatabaseService


@pytest.fixture
def sample_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "comboios.sqlite3"
    SampleDatabaseService(database_path).ensure_current()
    return database_path


def _service(database_path: Path) -> SampleDatabaseService:
    return SampleDatabaseService(database_path)


def test_sample_database_has_expected_tables_and_data(sample_database: Path) -> None:
    with sqlite3.connect(sample_database) as connection:
        table_names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("comboios", "estacoes", "viagens", "registos_atraso")
        }

    assert table_names == {
        "comboios",
        "estacoes",
        "viagens",
        "registos_atraso",
    }
    assert counts["comboios"] == 30
    assert counts["estacoes"] == 30
    assert counts["viagens"] == 3600
    assert counts["registos_atraso"] > 5000


def test_sample_database_covers_multiple_statuses_and_a_wide_date_range(
    sample_database: Path,
) -> None:
    with sqlite3.connect(sample_database) as connection:
        statuses = dict(
            connection.execute("SELECT estado, COUNT(*) FROM viagens GROUP BY estado").fetchall()
        )
        date_range = connection.execute(
            "SELECT MIN(data_viagem), MAX(data_viagem) FROM viagens"
        ).fetchone()
        train_count = connection.execute(
            "SELECT COUNT(DISTINCT id_comboio) FROM viagens"
        ).fetchone()[0]

    assert set(statuses) == {"Realizada", "Suprimida", "Planeada"}
    assert statuses["Realizada"] > 2500
    assert statuses["Suprimida"] > 100
    assert statuses["Planeada"] > 500
    assert date_range == ("2026-07-01", "2026-10-28")
    assert train_count == 30


def test_sample_database_has_no_broken_foreign_keys(sample_database: Path) -> None:
    with sqlite3.connect(sample_database) as connection:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert violations == []


def test_unchanged_database_is_not_replaced(tmp_path: Path) -> None:
    database_path = tmp_path / "comboios.sqlite3"

    assert _service(database_path).ensure_current() is True
    original_contents = database_path.read_bytes()

    assert _service(database_path).ensure_current() is False
    assert database_path.read_bytes() == original_contents


def test_changed_database_is_replaced(tmp_path: Path) -> None:
    database_path = tmp_path / "comboios.sqlite3"
    service = _service(database_path)
    service.ensure_current()

    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute("DELETE FROM comboios WHERE id_comboio = 1")

    assert service.ensure_current() is True
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM comboios").fetchone()[0] == 30


def test_missing_database_is_created(tmp_path: Path) -> None:
    database_path = tmp_path / "new" / "comboios.sqlite3"

    assert _service(database_path).ensure_current() is True
    assert database_path.is_file()


def test_corrupt_database_is_replaced(tmp_path: Path) -> None:
    database_path = tmp_path / "comboios.sqlite3"
    database_path.write_bytes(b"not a sqlite database")

    assert _service(database_path).ensure_current() is True
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM comboios").fetchone()[0] == 30
