import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

from text_to_sql.llms.llm_sql_generator.llm_sql_generator_model import SQLParameter


class SQLRepairResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sql: str = Field(min_length=1)
    parameters: list[SQLParameter] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_repaired_query(self) -> SQLRepairResult:
        normalized_sql = self.sql.strip()
        if re.match(r"^SELECT\b", normalized_sql, re.IGNORECASE) is None:
            raise ValueError("Repaired SQL must be a read-only SELECT query.")
        statement = normalized_sql.removesuffix(";").strip()
        if ";" in statement:
            raise ValueError("Repaired SQL must contain exactly one statement.")

        parameter_names = [parameter.name for parameter in self.parameters]
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("SQL parameter names must be unique.")
        placeholders = set(re.findall(r"(?<!:):([A-Za-z_]\w*)", normalized_sql))
        if placeholders != set(parameter_names):
            raise ValueError("SQL named placeholders must exactly match the supplied parameters.")

        object.__setattr__(self, "sql", normalized_sql)
        return self
