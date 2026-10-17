from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from text_to_sql.entity_resolution import EntityResolutionService, normalize_text
from text_to_sql.interaction_logs import InteractionLogService
from text_to_sql.llms.llm_selector import (
    LLMSelectorService,
    QuestionClassificationResult,
    QuestionClassificationResults,
)
from text_to_sql.sample_database import SampleDatabaseService
from text_to_sql.sqlite_db import SQLiteConfig, SQLiteService


@pytest.fixture
def resolver(tmp_path: Path) -> EntityResolutionService:
    database_path = tmp_path / "trains.db"
    SampleDatabaseService(database_path).ensure_current()
    return EntityResolutionService(SQLiteService(SQLiteConfig(database_path=database_path)))


def test_normalize_text_removes_accents_case_and_punctuation() -> None:
    assert normalize_text("  Porto - Campanhã! ") == "porto campanha"


def test_accent_and_case_differences_are_corrected(resolver: EntityResolutionService) -> None:
    result = resolver.run("Atrasos em evora para o comboio intercidade")

    canonicals = {entity.canonical for entity in result.entities}
    assert canonicals == {"Évora", "Intercidades"}
    assert result.suggestions == []


def test_station_partial_name_and_typo_are_resolved(resolver: EntityResolutionService) -> None:
    result = resolver.run("Viagens de Campanha para Coimbra B")

    canonicals = {entity.canonical for entity in result.entities}
    assert canonicals == {"Porto - Campanhã", "Coimbra-B"}


def test_small_typo_is_corrected(resolver: EntityResolutionService) -> None:
    result = resolver.run("Quantas viagens saem de Santarem?")

    assert [entity.canonical for entity in result.entities] == ["Santarém"]


def test_city_name_is_flagged_as_not_a_station(resolver: EntityResolutionService) -> None:
    result = resolver.run("Qual o horário de partida dos comboios no porto?")

    assert len(result.entities) == 1
    entity = result.entities[0]
    assert entity.canonical == "Porto"
    assert "estacoes.cidade" in entity.columns
    assert entity.stations == ["Porto - Campanhã"]
    hints = result.to_prompt_hints()
    assert "estacoes.nome = 'Porto'" in hints
    assert "Porto - Campanhã" in hints


def test_city_with_several_stations_lists_them(resolver: EntityResolutionService) -> None:
    result = resolver.run("Viagens em Lisboa")

    assert result.entities[0].stations == ["Lisboa - Santa Apolónia", "Lisboa - Oriente"]


def test_partial_name_resolves_to_full_name(resolver: EntityResolutionService) -> None:
    result = resolver.run("Quais os horários de partida de famalicão")

    assert [entity.canonical for entity in result.entities] == ["Vila Nova de Famalicão"]
    assert "'famalicão' é 'Vila Nova de Famalicão'" in result.to_prompt_hints()


def test_partial_alias_does_not_override_existing_names(resolver: EntityResolutionService) -> None:
    result = resolver.run("Viagens em Lisboa")

    assert [entity.canonical for entity in result.entities] == ["Lisboa"]
    assert result.suggestions == []


def test_unknown_words_are_left_alone(resolver: EntityResolutionService) -> None:
    result = resolver.run("Qual foi o maior atraso em outubro de 2026?")

    assert result.entities == []
    assert result.suggestions == []
    assert result.to_prompt_hints() == ""


def test_train_codes_are_never_fuzzy_matched(resolver: EntityResolutionService) -> None:
    exact = resolver.run("atraso do ic 523")
    assert [entity.canonical for entity in exact.entities] == ["IC523"]

    other = resolver.run("atraso do IC524")
    assert other.entities == []


def test_doubtful_match_becomes_a_suggestion(resolver: EntityResolutionService) -> None:
    result = resolver.run("Viagens para Vila Nova de Famalicao e Nine")

    assert any(entity.canonical == "Vila Nova de Famalicão" for entity in result.entities) or any(
        "Vila Nova de Famalicão" in s.candidates for s in result.suggestions
    )


def test_hints_ask_for_confirmation_on_doubts() -> None:
    from text_to_sql.entity_resolution import (
        EntityResolutionResult,
        EntitySuggestion,
        ResolvedEntity,
    )

    hints = EntityResolutionResult(
        entities=[ResolvedEntity(original="evora", canonical="Évora", kind="estacao", score=1)],
        suggestions=[EntitySuggestion(original="Lisb", candidates=["Lisboa", "Lagos"])],
    ).to_prompt_hints()

    assert "'evora' é 'Évora'" in hints
    assert "'Lisb' pode ser 'Lisboa' ou 'Lagos'" in hints
    assert "status='ambiguous'" in hints


def test_selector_appends_entity_hints_to_instructions(resolver: EntityResolutionService) -> None:
    parsed = QuestionClassificationResult(status="relevant", normalized_query="Viagens em Évora")
    client = Mock()
    client.responses.parse.return_value = Mock(
        output_parsed=QuestionClassificationResults(classifications=[parsed])
    )
    logs = InteractionLogService()

    with patch("text_to_sql.llms.common.OpenAI", return_value=client):
        selector = LLMSelectorService(
            api_key="test-key",
            model="test-model",
            interaction_logs=logs,
            entity_resolver=resolver,
        )
        selector.classify_question("Viagens em evora")

    instructions = client.responses.parse.call_args.kwargs["instructions"]
    assert "'evora' é 'Évora'" in instructions
    entry = next(e for e in logs.entries if e.component == "entity_resolution")
    assert entry.event == "entities_resolved"
    assert entry.details["question"] == "Viagens em evora"
    assert entry.details["entities"][0]["canonical"] == "Évora"
    assert "'evora' é 'Évora'" in entry.details["hints"]


def test_selector_logs_when_nothing_needs_correcting(resolver: EntityResolutionService) -> None:
    parsed = QuestionClassificationResult(status="relevant", normalized_query="Quantas viagens?")
    client = Mock()
    client.responses.parse.return_value = Mock(
        output_parsed=QuestionClassificationResults(classifications=[parsed])
    )
    logs = InteractionLogService()

    with patch("text_to_sql.llms.common.OpenAI", return_value=client):
        LLMSelectorService(
            api_key="test-key",
            model="test-model",
            interaction_logs=logs,
            entity_resolver=resolver,
        ).classify_question("Quantas viagens?")

    assert [e.event for e in logs.entries if e.component == "entity_resolution"] == [
        "no_entity_changes"
    ]
