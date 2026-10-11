import re

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SQLCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(min_length=1)
    chunk_id: str = Field(min_length=1)
    quote: str = Field(min_length=1)


class SQLParameter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, pattern=r"^[A-Za-z_]\w*$")
    value: str | int | float | None


class SQLGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answerable: bool
    sql: str | None = None
    parameters: list[SQLParameter] = Field(default_factory=list)
    explanation: str = Field(min_length=1)
    citations: list[SQLCitation] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_generation(self) -> SQLGenerationResult:
        parameter_names = [parameter.name for parameter in self.parameters]
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("SQL parameter names must be unique.")
        if self.answerable:
            if not self.sql or not self.sql.strip():
                raise ValueError("An answerable result must contain a SQL query.")
            normalized_sql = self.sql.strip()
            if re.match(r"^SELECT\b", normalized_sql, re.IGNORECASE) is None:
                raise ValueError("Generated SQL must be a read-only SELECT query.")
            statement = normalized_sql.removesuffix(";").strip()
            if ";" in statement:
                raise ValueError("Generated SQL must contain exactly one statement.")
            if not self.citations:
                raise ValueError("An answerable result must include at least one citation.")
            placeholders = set(re.findall(r"(?<!:):([A-Za-z_]\w*)", normalized_sql))
            # Parâmetros não usados no SQL são inofensivos e descartados.
            used_parameters = [p for p in self.parameters if p.name in placeholders]
            if len(used_parameters) != len(self.parameters):
                object.__setattr__(self, "parameters", used_parameters)
                parameter_names = [parameter.name for parameter in used_parameters]
            if placeholders != set(parameter_names):
                raise ValueError(
                    "SQL named placeholders must exactly match the supplied parameters."
                )
            object.__setattr__(self, "sql", normalized_sql)
        elif self.sql is not None or self.parameters or self.citations:
            # O modelo por vezes preenche SQL ao declarar a pergunta não respondível;
            # descarta-se para que o ciclo de retries use a explicação.
            object.__setattr__(self, "sql", None)
            object.__setattr__(self, "parameters", [])
            object.__setattr__(self, "citations", [])
        return self
