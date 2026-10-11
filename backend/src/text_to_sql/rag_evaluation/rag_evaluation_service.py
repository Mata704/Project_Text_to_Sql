from collections.abc import Sequence
from math import isfinite
from statistics import mean

import tiktoken
from pydantic import BaseModel, ConfigDict, Field, model_validator

from text_to_sql.chunking.constants import TOKENIZER_ENCODING
from text_to_sql.constants import UNKNOWN_SOURCE
from text_to_sql.retrieval.retrieval_model import RetrievedChunk


class RAGEvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    expected_sources: tuple[str, ...] = ()
    expected_facts: tuple[str, ...] = ()
    should_answer: bool

    @model_validator(mode="after")
    def validate_answerable_case(self) -> RAGEvaluationCase:
        if self.should_answer and (not self.expected_sources or not self.expected_facts):
            raise ValueError("Answerable RAG cases require expected sources and expected facts.")
        if len(self.expected_sources) != len(set(self.expected_sources)):
            raise ValueError("Expected sources must be unique.")
        if len(self.expected_facts) != len(set(self.expected_facts)):
            raise ValueError("Expected facts must be unique.")
        if any(not value.strip() for value in (*self.expected_sources, *self.expected_facts)):
            raise ValueError("Expected sources and facts cannot be empty strings.")
        return self


class EvaluatedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str
    answerable: bool
    sources: tuple[str, ...] = ()


class RAGEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    retrieval_source_precision: float | None = Field(default=None, ge=0, le=1)
    retrieval_source_recall: float | None = Field(default=None, ge=0, le=1)
    retrieval_mrr: float | None = Field(default=None, ge=0, le=1)
    fact_coverage: float | None = Field(default=None, ge=0, le=1)
    answerability_correct: float = Field(ge=0, le=1)
    citation_validity: float = Field(ge=0, le=1)
    citation_source_recall: float | None = Field(default=None, ge=0, le=1)
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

        retrieved_sources = [
            str(item.chunk.metadata.get("source", UNKNOWN_SOURCE)) for item in retrieved_chunks
        ]
        unique_retrieved_sources = set(retrieved_sources)
        return RAGEvaluationResult(
            case_id=case.case_id,
            retrieval_source_precision=self._source_precision(
                unique_retrieved_sources,
                case.expected_sources,
            ),
            retrieval_source_recall=self._source_recall(
                unique_retrieved_sources,
                case.expected_sources,
            ),
            retrieval_mrr=self._source_mrr(retrieved_sources, case.expected_sources),
            fact_coverage=self._fact_coverage(answer.answer, case.expected_facts),
            answerability_correct=float(answer.answerable == case.should_answer),
            citation_validity=self._citation_validity(answer, unique_retrieved_sources),
            citation_source_recall=self._citation_source_recall(
                answer,
                case.expected_sources,
            ),
            latency_ms=latency_ms,
            context_tokens=self._context_token_count(retrieved_chunks),
        )

    def summarize(
        self,
        results: Sequence[RAGEvaluationResult],
    ) -> dict[str, float | None]:
        if not results:
            raise ValueError("At least one RAG evaluation result is required.")

        metric_names = (
            "retrieval_source_precision",
            "retrieval_source_recall",
            "retrieval_mrr",
            "fact_coverage",
            "answerability_correct",
            "citation_validity",
            "citation_source_recall",
            "latency_ms",
            "context_tokens",
        )
        summary = {}
        for metric in metric_names:
            values = [value for result in results if (value := getattr(result, metric)) is not None]
            summary[metric] = mean(values) if values else None
        return summary

    def _source_precision(
        self,
        retrieved_sources: set[str],
        expected_sources: Sequence[str],
    ) -> float | None:
        if not expected_sources:
            return None
        if not retrieved_sources:
            return 0.0
        return len(retrieved_sources.intersection(expected_sources)) / len(retrieved_sources)

    def _source_recall(
        self,
        retrieved_sources: set[str],
        expected_sources: Sequence[str],
    ) -> float | None:
        if not expected_sources:
            return None
        return len(retrieved_sources.intersection(expected_sources)) / len(expected_sources)

    def _source_mrr(
        self,
        retrieved_sources: Sequence[str],
        expected_sources: Sequence[str],
    ) -> float | None:
        if not expected_sources:
            return None
        expected_source_set = set(expected_sources)
        for rank, source in enumerate(retrieved_sources, start=1):
            if source in expected_source_set:
                return 1 / rank
        return 0.0

    def _fact_coverage(self, answer: str, expected_facts: Sequence[str]) -> float | None:
        if not expected_facts:
            return None
        normalized_answer = " ".join(answer.casefold().split())
        covered_facts = sum(
            " ".join(fact.casefold().split()) in normalized_answer for fact in expected_facts
        )
        return covered_facts / len(expected_facts)

    def _citation_source_recall(
        self,
        answer: EvaluatedAnswer,
        expected_sources: Sequence[str],
    ) -> float | None:
        if not expected_sources:
            return None
        return len(set(answer.sources).intersection(expected_sources)) / len(expected_sources)

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
            f"[source={item.chunk.metadata.get('source', UNKNOWN_SOURCE)}; "
            f"chunk_id={item.chunk.chunk_id}; score={item.score:.3f}]\n"
            f"{item.chunk.content}"
            for item in retrieved_chunks
        )
        return len(self._tokenizer.encode(context))
