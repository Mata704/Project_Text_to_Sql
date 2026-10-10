from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from text_to_sql.sqlite_db.constants import DEFAULT_DATABASE_PATH


class SQLiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    database_path: Path = Field(default=DEFAULT_DATABASE_PATH)


class SQLiteWriteResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    row_count: int
    last_row_id: int | None = None
