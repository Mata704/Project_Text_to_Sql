from collections.abc import Sequence
from math import isfinite
from statistics import mean

import tiktoken
from pydantic import BaseModel, ConfigDict, Field

from text_to_sql.chunking.constants import TOKENIZER_ENCODING
from text_to_sql.retrieval.retrieval_model import RetrievedChunk


class RAGEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_sources: tuple[str, ...] = ()
    expected_facts: tuple[str, ...] = ()
    should_answer: bool


class EvaluatedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str
    answerable: bool
    sources: tuple[str, ...] = ()


class RAGEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    retrieval_source_recall: float = Field(ge=0, le=1)
    fact_coverage: float = Field(ge=0, le=1)
    answerability_correct: float = Field(ge=0, le=1)
    citation_validity: float = Field(ge=0, le=1)
    latency_ms: float = Field(ge=0)
    context_tokens: int = Field(ge=0)


class RAGEvaluationService:
    """Calculates reference-based RAG metrics for offline test runs."""

    def __init__(self) -> None:
        self._tokenizer = tiktoken.get_encoding(TOKENIZER_ENCODING)

    def evaluate(
        self,
        case: RAGEvaluationCase,
        retrieved_chunks: Sequence[RetrievedChunk],
        answer: EvaluatedAnswer,
        *,
        latency_ms: float,
    ) -> RAGEvaluationResult:
        if not isfinite(latency_ms) or latency_ms < 0:
            raise ValueError("Evaluation latency must be finite and non-negative.")

        retrieved_sources = {
            str(item.chunk.metadata.get("source", "unknown")) for item in retrieved_chunks
        }
        return RAGEvaluationResult(
            case_id=case.case_id,
            retrieval_source_recall=self._source_recall(
                retrieved_sources,
                case.expected_sources,
            ),
            fact_coverage=self._fact_coverage(answer.answer, case.expected_facts),
            answerability_correct=float(answer.answerable == case.should_answer),
            citation_validity=self._citation_validity(answer, retrieved_sources),
            latency_ms=latency_ms,
            context_tokens=self._context_token_count(retrieved_chunks),
        )

    def summarize(
        self,
        results: Sequence[RAGEvaluationResult],
    ) -> dict[str, float]:
        if not results:
            raise ValueError("At least one RAG evaluation result is required.")

        metric_names = (
            "retrieval_source_recall",
            "fact_coverage",
            "answerability_correct",
            "citation_validity",
            "latency_ms",
            "context_tokens",
        )
        return {
            metric: mean(getattr(result, metric) for result in results) for metric in metric_names
        }

    def _source_recall(
        self,
        retrieved_sources: set[str],
        expected_sources: Sequence[str],
    ) -> float:
        if not expected_sources:
            return 1.0
        return len(retrieved_sources.intersection(expected_sources)) / len(expected_sources)

    def _fact_coverage(self, answer: str, expected_facts: Sequence[str]) -> float:
        if not expected_facts:
            return 1.0
        normalized_answer = " ".join(answer.casefold().split())
        covered_facts = sum(
            " ".join(fact.casefold().split()) in normalized_answer for fact in expected_facts
        )
        return covered_facts / len(expected_facts)

    def _citation_validity(
        self,
        answer: EvaluatedAnswer,
        retrieved_sources: set[str],
    ) -> float:
        if not answer.answerable:
            return float(not answer.sources)
        if not answer.sources:
            return 0.0
        return float(set(answer.sources).issubset(retrieved_sources))

    def _context_token_count(self, retrieved_chunks: Sequence[RetrievedChunk]) -> int:
        context = "\n\n".join(
            f"[source={item.chunk.metadata.get('source', 'unknown')}; "
            f"chunk_id={item.chunk.chunk_id}; score={item.score:.3f}]\n"
            f"{item.chunk.content}"
            for item in retrieved_chunks
        )
        return len(self._tokenizer.encode(context))
