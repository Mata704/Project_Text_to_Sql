from pydantic import BaseModel, ConfigDict, Field


class ResolvedEntity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    original: str
    canonical: str
    kind: str
    columns: list[str] = Field(default_factory=list)
    stations: list[str] = Field(default_factory=list)
    score: float = Field(ge=0, le=1)


class EntitySuggestion(BaseModel):
    """Texto do utilizador com correspondência duvidosa na base de dados."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    original: str
    candidates: list[str] = Field(min_length=1)


class EntityResolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entities: list[ResolvedEntity] = Field(default_factory=list)
    suggestions: list[EntitySuggestion] = Field(default_factory=list)

    def to_prompt_hints(self) -> str:
        """Texto para o seletor: correções certas e dúvidas a confirmar com o utilizador."""
        lines: list[str] = []
        for entity in self.entities:
            if entity.canonical.casefold() != entity.original.casefold():
                lines.append(
                    f"- Corrigido: '{entity.original}' é '{entity.canonical}' ({entity.kind})."
                )
            if "estacao" not in entity.kind.split("/"):
                columns = " ou ".join(entity.columns)
                stations = " e ".join(f"'{station}'" for station in entity.stations)
                lines.append(
                    f"- Local: '{entity.canonical}' não é nome de estação; existe em {columns}. "
                    f"Estações nesse local: {stations or 'nenhuma'}. Nunca uses "
                    f"estacoes.nome = '{entity.canonical}'. Se o pedido for sobre o local, "
                    f"escreve em normalized_query 'a cidade/o distrito de {entity.canonical}' "
                    "(filtrando por estacoes.cidade ou estacoes.distrito); se o utilizador "
                    "pedir uma estação específica e só houver uma, usa o nome dessa estação; "
                    "se houver várias, devolve status='ambiguous' e pergunta qual."
                )
        for suggestion in self.suggestions:
            options = " ou ".join(f"'{candidate}'" for candidate in suggestion.candidates)
            lines.append(f"- Dúvida: '{suggestion.original}' pode ser {options}.")
        if not lines:
            return ""
        return (
            "Verificação automática de nomes contra a base de dados:\n"
            + "\n".join(lines)
            + "\nPara 'Corrigido', usa exatamente o nome indicado em normalized_query. "
            "Para 'Dúvida', não escolhas: devolve status='ambiguous' com uma única "
            "clarification_question curta a perguntar se o utilizador se refere a cada "
            "opção (por exemplo \"Quer dizer 'X'?\"). Se a mensagem atual ou o histórico "
            "já confirmar uma opção, usa-a em normalized_query."
        )
