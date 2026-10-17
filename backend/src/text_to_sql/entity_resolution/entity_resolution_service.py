import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from text_to_sql.entity_resolution.constants import (
    AMBIGUITY_MARGIN,
    COLUMN_BY_KIND,
    DOUBT_MIN_RATIO,
    ENTITY_SOURCES,
    EXACT_ONLY_KINDS,
    FUZZY_MIN_LENGTH,
    MANUAL_ALIASES,
    MAX_DOUBT_CANDIDATES,
    MIN_PARTIAL_WORD_LENGTH,
    PARTIAL_NAME_KINDS,
    PLACE_KINDS,
    RESOLVED_MIN_RATIO,
    STATION_SEPARATOR,
    STOPWORDS,
)
from text_to_sql.entity_resolution.entity_resolution_model import (
    EntityResolutionResult,
    EntitySuggestion,
    ResolvedEntity,
)
from text_to_sql.sqlite_db import SQLiteService

_TOKEN_PATTERN = re.compile(r"\w+")


def normalize_text(text: str) -> str:
    """Minúsculas, sem acentos nem pontuação, com espaços colapsados."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[\W_]+", " ", without_accents).split())


def _squash(normalized: str) -> str:
    # Ignora espaços para que "coimbra b" e "coimbrab" casem com "Coimbra-B".
    return normalized.replace(" ", "")


@dataclass
class _Index:
    aliases: dict[str, set[tuple[str, str]]] = field(default_factory=dict)
    stations_by_place: dict[str, list[str]] = field(default_factory=dict)
    max_words: int = 1

    def add(self, alias: str, kind: str, canonical: str) -> None:
        normalized = normalize_text(alias)
        if not normalized:
            return
        self.aliases.setdefault(_squash(normalized), set()).add((kind, canonical))
        self.max_words = max(self.max_words, len(normalized.split()))


class EntityResolutionService:
    """Compara nomes da pergunta com os valores reais da base de dados."""

    def __init__(self, sqlite_service: SQLiteService | None = None) -> None:
        self.sqlite_service = sqlite_service or SQLiteService()
        self._index: _Index | None = None

    def refresh(self) -> None:
        self._index = None

    def run(self, question: str) -> EntityResolutionResult:
        index = self._get_index()
        tokens = [
            (match.start(), match.end(), normalize_text(match.group()))
            for match in _TOKEN_PATTERN.finditer(question)
        ]
        tokens = [token for token in tokens if token[2]]
        used = [False] * len(tokens)
        entities: list[ResolvedEntity] = []
        suggestions: list[EntitySuggestion] = []

        for size in range(min(index.max_words, len(tokens)), 0, -1):
            for first in range(len(tokens) - size + 1):
                last = first + size - 1
                if any(used[first : last + 1]):
                    continue
                words = [token[2] for token in tokens[first : last + 1]]
                if all(word in STOPWORDS for word in words):
                    continue
                outcome = self._match_window(words, index)
                if outcome is None:
                    continue
                original = question[tokens[first][0] : tokens[last][1]]
                used[first : last + 1] = [True] * size
                if isinstance(outcome, ResolvedEntity):
                    changed = outcome.canonical.casefold() != original.casefold()
                    # Cidades/distritos iguais ao texto também são sinalizados: não são
                    # nomes de estações e o SQL não pode filtrar por estacoes.nome.
                    place_only = bool(outcome.stations) or (
                        "estacao" not in outcome.kind.split("/")
                        and any(kind in PLACE_KINDS for kind in outcome.kind.split("/"))
                    )
                    if changed or place_only:
                        entities.append(outcome.model_copy(update={"original": original}))
                else:
                    suggestions.append(EntitySuggestion(original=original, candidates=outcome))

        return EntityResolutionResult(entities=entities, suggestions=suggestions)

    def _match_window(
        self,
        words: list[str],
        index: _Index,
    ) -> ResolvedEntity | list[str] | None:
        key = _squash(" ".join(words))
        exact = index.aliases.get(key)
        if exact:
            return self._exact(exact, index)

        if len(key) < FUZZY_MIN_LENGTH or not re.search(r"[a-z]", key):
            return None
        if words[0] in STOPWORDS or words[-1] in STOPWORDS:
            return None

        scored: dict[str, tuple[float, str]] = {}
        for alias, candidates in index.aliases.items():
            if abs(len(alias) - len(key)) > max(2, len(key) // 4):
                continue
            fuzzy_candidates = [c for c in candidates if c[0] not in EXACT_ONLY_KINDS]
            if not fuzzy_candidates:
                continue
            ratio = SequenceMatcher(None, key, alias).ratio()
            if ratio < DOUBT_MIN_RATIO:
                continue
            for kind, canonical in fuzzy_candidates:
                if canonical not in scored or ratio > scored[canonical][0]:
                    scored[canonical] = (ratio, kind)
        if not scored:
            return None

        ranked = sorted(scored.items(), key=lambda item: item[1][0], reverse=True)
        best_canonical, (best_score, best_kind) = ranked[0]
        runner_up = ranked[1][1][0] if len(ranked) > 1 else 0.0
        if best_score >= RESOLVED_MIN_RATIO and best_score - runner_up > AMBIGUITY_MARGIN:
            return ResolvedEntity(
                original=key,
                canonical=best_canonical,
                kind=best_kind,
                columns=[COLUMN_BY_KIND[best_kind]],
                stations=index.stations_by_place.get(best_canonical, [])
                if best_kind in PLACE_KINDS
                else [],
                score=round(best_score, 3),
            )
        return [canonical for canonical, _ in ranked[:MAX_DOUBT_CANDIDATES]]

    @staticmethod
    def _exact(
        candidates: set[tuple[str, str]],
        index: _Index,
    ) -> ResolvedEntity | list[str]:
        canonicals = sorted({canonical for _, canonical in candidates})
        if len(canonicals) > 1:
            return canonicals[:MAX_DOUBT_CANDIDATES]
        kinds = sorted(kind for kind, _ in candidates)
        canonical = canonicals[0]
        return ResolvedEntity(
            original=canonical,
            canonical=canonical,
            kind="/".join(kinds),
            columns=[COLUMN_BY_KIND[kind] for kind in kinds],
            stations=index.stations_by_place.get(canonical, []) if "estacao" not in kinds else [],
            score=1.0,
        )

    @staticmethod
    def _multi_word_places(index: _Index) -> list[tuple[str, str]]:
        return sorted(
            {
                (kind, canonical)
                for candidates in index.aliases.values()
                for kind, canonical in candidates
                if kind in PARTIAL_NAME_KINDS and len(canonical.split()) > 1
            }
        )

    def _get_index(self) -> _Index:
        if self._index is None:
            self._index = self._build_index()
        return self._index

    def _build_index(self) -> _Index:
        index = _Index()
        for kind, table, column in ENTITY_SOURCES:
            rows = self.sqlite_service.fetch_all(
                f"SELECT DISTINCT {column} AS value FROM {table} "  # noqa: S608
                f"WHERE {column} IS NOT NULL"
            )
            for row in rows:
                value = str(row["value"]).strip()
                if not value:
                    continue
                index.add(value, kind, value)
                if kind == "estacao" and STATION_SEPARATOR in value:
                    # "Lisboa - Oriente" também pode ser escrito só como "Oriente".
                    index.add(value.split(STATION_SEPARATOR, 1)[1], kind, value)

        partial_aliases: dict[str, set[tuple[str, str]]] = {}
        for row in self.sqlite_service.fetch_all("SELECT nome, cidade, distrito FROM estacoes"):
            for place in {str(row["cidade"]), str(row["distrito"])}:
                index.stations_by_place.setdefault(place, []).append(str(row["nome"]))

        for kind, canonical in self._multi_word_places(index):
            for word in normalize_text(canonical).split():
                key = _squash(word)
                # Só palavras distintivas que não colidam com um nome já existente.
                if len(key) >= MIN_PARTIAL_WORD_LENGTH and word not in STOPWORDS:
                    partial_aliases.setdefault(key, set()).add((kind, canonical))
        for key, candidates in partial_aliases.items():
            if key not in index.aliases:
                for kind, canonical in candidates:
                    index.add(key, kind, canonical)

        known = {canonical for candidates in index.aliases.values() for _, canonical in candidates}
        for alias, (kind, canonical) in MANUAL_ALIASES.items():
            if canonical in known:
                index.add(alias, kind, canonical)
        return index
