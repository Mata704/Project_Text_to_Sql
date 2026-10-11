from pydantic import BaseModel, ConfigDict, Field

SQLiteValue = str | int | float | None


class SQLExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    succeeded: bool
    sql: str
    parameters: dict[str, SQLiteValue]
    rows: list[dict[str, object]] = Field(default_factory=list)
    attempts: int
