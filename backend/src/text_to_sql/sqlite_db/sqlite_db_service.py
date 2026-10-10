import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from pathlib import Path

from text_to_sql.errors import SQLiteDatabaseError
from text_to_sql.sqlite_db.sqlite_db_model import SQLiteConfig, SQLiteWriteResult

SQLiteParameter = str | int | float | bytes | None
SQLiteParameters = Sequence[SQLiteParameter] | Mapping[str, SQLiteParameter]


class SQLiteService:
    def __init__(self, config: SQLiteConfig | None = None) -> None:
        self.config = config or SQLiteConfig()

    def fetch_all(
        self,
        query: str,
        parameters: SQLiteParameters = (),
    ) -> list[dict[str, object]]:
        self._validate_query(query)
        database_path = self._existing_database_path()
        try:
            with closing(self._connect_read_only(database_path)) as connection:
                rows = connection.execute(query, parameters).fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as error:
            raise SQLiteDatabaseError(f"Could not read from SQLite: {error}") from error

    def fetch_one(
        self,
        query: str,
        parameters: SQLiteParameters = (),
    ) -> dict[str, object] | None:
        self._validate_query(query)
        database_path = self._existing_database_path()
        try:
            with closing(self._connect_read_only(database_path)) as connection:
                row = connection.execute(query, parameters).fetchone()
                return dict(row) if row is not None else None
        except sqlite3.Error as error:
            raise SQLiteDatabaseError(f"Could not read from SQLite: {error}") from error

    def execute(
        self,
        query: str,
        parameters: SQLiteParameters = (),
    ) -> SQLiteWriteResult:
        self._validate_query(query)
        database_path = self._existing_database_path()
        try:
            with closing(self._connect(database_path)) as connection, connection:
                cursor = connection.execute(query, parameters)
                return SQLiteWriteResult(
                    row_count=cursor.rowcount,
                    last_row_id=cursor.lastrowid,
                )
        except sqlite3.Error as error:
            raise SQLiteDatabaseError(f"Could not write to SQLite: {error}") from error

    def execute_many(
        self,
        query: str,
        parameters: Sequence[Sequence[SQLiteParameter]],
    ) -> SQLiteWriteResult:
        self._validate_query(query)
        if not parameters:
            return SQLiteWriteResult(row_count=0)

        database_path = self._existing_database_path()
        try:
            with closing(self._connect(database_path)) as connection, connection:
                cursor = connection.executemany(query, parameters)
                return SQLiteWriteResult(row_count=cursor.rowcount)
        except sqlite3.Error as error:
            raise SQLiteDatabaseError(f"Could not write to SQLite: {error}") from error

    def _existing_database_path(self) -> Path:
        database_path = self.config.database_path.resolve()
        if not database_path.is_file():
            raise SQLiteDatabaseError(f"SQLite database does not exist: {database_path}")
        return database_path

    def _connect(self, database_path: Path) -> sqlite3.Connection:
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _connect_read_only(self, database_path: Path) -> sqlite3.Connection:
        database_uri = f"{database_path.as_uri()}?mode=ro"
        connection = sqlite3.connect(database_uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def _validate_query(self, query: str) -> None:
        if not query.strip():
            raise ValueError("The SQLite query cannot be empty.")
