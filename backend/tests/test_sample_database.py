import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from scripts.create_sample_database import create_database


@pytest.fixture
def sample_database(tmp_path: Path) -> Path:
    database_path = tmp_path / "comboios.sqlite3"
    create_database(database_path)
    return database_path


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
    assert counts["comboios"] == 10
    assert counts["estacoes"] == 12
    assert counts["viagens"] == 100
    assert counts["registos_atraso"] > 0


def test_sample_database_has_no_broken_foreign_keys(sample_database: Path) -> None:
    with sqlite3.connect(sample_database) as connection:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert violations == []


def test_unchanged_database_is_not_replaced(tmp_path: Path) -> None:
    database_path = tmp_path / "comboios.sqlite3"

    assert create_database(database_path) is True
    original_contents = database_path.read_bytes()

    assert create_database(database_path) is False
    assert database_path.read_bytes() == original_contents


def test_changed_database_is_replaced(tmp_path: Path) -> None:
    database_path = tmp_path / "comboios.sqlite3"
    create_database(database_path)

    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute("DELETE FROM comboios WHERE id_comboio = 1")

    assert create_database(database_path) is True
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM comboios").fetchone()[0] == 10


def test_missing_database_is_created(tmp_path: Path) -> None:
    database_path = tmp_path / "new" / "comboios.sqlite3"

    assert create_database(database_path) is True
    assert database_path.is_file()


def test_corrupt_database_is_replaced(tmp_path: Path) -> None:
    database_path = tmp_path / "comboios.sqlite3"
    database_path.write_bytes(b"not a sqlite database")

    assert create_database(database_path) is True
    with sqlite3.connect(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM comboios").fetchone()[0] == 10
