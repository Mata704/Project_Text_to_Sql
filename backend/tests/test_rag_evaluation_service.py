import json
from pathlib import Path

import pytest

from text_to_sql.rag_evaluation import (
    EvaluatedAnswer,
    RAGEvaluationCase,
    RAGEvaluationService,
)
from text_to_sql.retrieval import RetrievedChunk
from text_to_sql.vector_store import StoredChunk

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "rag_evaluation_cases.json"


def _retrieved(source: str, content: str, chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk=StoredChunk(
            chunk_id=chunk_id,
            content=content,
            metadata={"source": source},
        ),
        score=0.9,
    )


def test_rag_evaluation_calculates_reference_metrics_for_a_case() -> None:
    service = RAGEvaluationService()
    cases = [
        RAGEvaluationCase.model_validate(item)
        for item in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    ]
    case = cases[0]
    assert case.case_id == "arrival-delay-filter"
    retrieved = [
        _retrieved(
            "tables/registos_atraso.md",
            "Para atrasos de chegada, filtre tipo_registo = 'Chegada'.",
            "delays-001",
        ),
        _retrieved(
            "README.md",
            "Para calcular atrasos efetivos, filtrar estado = 'Realizada'.",
            "rules-001",
        ),
    ]
    answer = EvaluatedAnswer(
        answer=(
            "Use tipo_registo = 'Chegada' e filtre estado = 'Realizada' "
            "para considerar atrasos efetivos."
        ),
        answerable=True,
        sources=("tables/registos_atraso.md",),
    )

    result = service.evaluate(case, retrieved, answer, latency_ms=125.0)

    assert result.retrieval_source_recall == 1.0
    assert result.fact_coverage == 1.0
    assert result.answerability_correct == 1.0
    assert result.citation_validity == 1.0
    assert result.latency_ms == 125.0
    assert result.context_tokens > 0


def test_rag_evaluation_scores_a_no_reference_question_as_unanswerable() -> None:
    service = RAGEvaluationService()
    cases = [
        RAGEvaluationCase.model_validate(item)
        for item in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    ]
    case = cases[1]

    result = service.evaluate(
        case,
        [],
        EvaluatedAnswer(answer="A documentação não indica preços.", answerable=False),
        latency_ms=15.0,
    )

    assert result.retrieval_source_recall == 1.0
    assert result.fact_coverage == 1.0
    assert result.answerability_correct == 1.0
    assert result.citation_validity == 1.0


def test_rag_evaluation_detects_missing_sources_facts_and_invalid_citations() -> None:
    service = RAGEvaluationService()
    case = RAGEvaluationCase(
        case_id="missing-source",
        question="Qual o estado de uma viagem?",
        expected_sources=("tables/viagens.md",),
        expected_facts=("Planeada", "Realizada"),
        should_answer=False,
    )
    retrieved = [_retrieved("tables/comboios.md", "Tipos de comboio.", "trains-001")]
    answer = EvaluatedAnswer(
        answer="Não sei.",
        answerable=True,
        sources=("tables/not-retrieved.md",),
    )

    result = service.evaluate(case, retrieved, answer, latency_ms=10.0)

    assert result.retrieval_source_recall == 0.0
    assert result.fact_coverage == 0.0
    assert result.answerability_correct == 0.0
    assert result.citation_validity == 0.0


def test_rag_evaluation_summarizes_case_metrics_and_rejects_empty_results() -> None:
    service = RAGEvaluationService()
    case = RAGEvaluationCase(
        case_id="no-reference",
        question="Pergunta fora das fontes?",
        should_answer=False,
    )
    result = service.evaluate(
        case,
        [],
        EvaluatedAnswer(answer="", answerable=False),
        latency_ms=20,
    )

    summary = service.summarize([result, result])

    assert summary["answerability_correct"] == 1.0
    assert summary["citation_validity"] == 1.0
    assert summary["latency_ms"] == 20.0
    with pytest.raises(ValueError, match="At least one"):
        service.summarize([])
