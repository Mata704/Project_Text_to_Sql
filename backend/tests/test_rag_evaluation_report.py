import json
import os
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import pytest

from text_to_sql.config import Settings
from text_to_sql.document_ingestion import DocumentIngestionConfig, DocumentIngestionService
from text_to_sql.embeddings import EmbeddingService
from text_to_sql.embeddings.embedding_model import EmbeddingConfig
from text_to_sql.rag_evaluation import RAGEvaluationCase, RAGEvaluationService
from text_to_sql.retrieval import RetrievedChunk

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "rag_evaluation_cases.json"
REPORT_PATH = Path(__file__).parents[1] / "reports" / "rag-evaluation-latest.md"
TOP_K_VALUES = (3, 5, 8)
SIMILARITY_THRESHOLDS = (None, 0.15, 0.45, 0.50, 0.55, 0.60)


def _format_metric(value: float | int | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def _render_report(
    *,
    cases: list[RAGEvaluationCase],
    summaries: dict[tuple[int, float | None], dict[str, float | int | None]],
    case_results: dict[str, list[tuple[RetrievedChunk, ...]]],
    corpus_chunks: int,
    embedding_model: str,
    query_embedding_seconds: float,
    evaluator: RAGEvaluationService,
) -> str:
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# Avaliação RAG",
        "",
        f"- Gerado em: `{generated_at}`",
        f"- Casos: {len(cases)} ({sum(case.should_answer for case in cases)} respondíveis, "
        f"{sum(not case.should_answer for case in cases)} sem suporte esperado)",
        f"- Chunks indexados: {corpus_chunks}",
        f"- Modelo de embeddings: `{embedding_model}`",
        f"- Tempo para gerar embeddings das perguntas: {query_embedding_seconds:.3f} s",
        "",
        "## Comparação de `top_k` e threshold",
        "",
        "| `top_k` | Threshold | Precisão fontes | Recall fontes | MRR | "
        "Chunks médios | Tokens médios | Latência retrieval (ms) | "
        "Respondíveis sem resultados | Sem suporte sem resultados |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for top_k in TOP_K_VALUES:
        for threshold in SIMILARITY_THRESHOLDS:
            summary = summaries[(top_k, threshold)]
            label = "nenhum" if threshold is None else f"{threshold:.2f}"
            lines.append(
                f"| {top_k} | {label} "
                f"| {_format_metric(summary['retrieval_source_precision'])} "
                f"| {_format_metric(summary['retrieval_source_recall'])} "
                f"| {_format_metric(summary['retrieval_mrr'])} "
                f"| {summary['retrieved_chunks']:.2f} "
                f"| {summary['context_tokens']:.0f} "
                f"| {summary['latency_ms']:.2f} "
                f"| {summary['answerable_empty']} "
                f"| {summary['unsupported_empty']} |"
            )

    lines.extend(
        [
            "",
            "## Casos com `top_k=5` e threshold `0,15`",
            "",
            "| Caso | Respondível | Recall fontes | MRR | Chunks | Score máximo | "
            "Fontes esperadas | Fontes recuperadas |",
            "|---|:---:|---:|---:|---:|---:|---|---|",
        ]
    )

    for case in cases:
        retrieved = case_results[case.case_id][0]
        result = evaluator.evaluate_retrieval(case, retrieved, latency_ms=0)
        retrieved_sources = list(
            dict.fromkeys(str(item.chunk.metadata.get("source", "unknown")) for item in retrieved)
        )
        expected_sources = ", ".join(case.expected_sources) or "n/a"
        found_sources = ", ".join(retrieved_sources) or "nenhuma"
        max_score = max((item.score for item in retrieved), default=None)
        lines.append(
            f"| `{case.case_id}` | {'sim' if case.should_answer else 'não'} "
            f"| {_format_metric(result.retrieval_source_recall)} "
            f"| {_format_metric(result.retrieval_mrr)} "
            f"| {len(retrieved)} "
            f"| {_format_metric(max_score)} "
            f"| {expected_sources} | {found_sources} |"
        )

    lines.append("")
    return "\n".join(lines)


@pytest.mark.integration
@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_RAG_EVALUATION") != "1",
    reason="Set RUN_LIVE_RAG_EVALUATION=1 to run the live evaluation.",
)
def test_rag_evaluation_cases_generate_markdown_report() -> None:
    case_data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = [RAGEvaluationCase.model_validate(item) for item in case_data]
    settings = Settings()
    api_key = (
        settings.openai_api_key.get_secret_value() if settings.openai_api_key is not None else ""
    )
    if not api_key.strip():
        pytest.fail("Configure OPENAI_API_KEY in backend/.env to run the live RAG evaluation.")

    embedding_config = EmbeddingConfig(model=settings.openai_embedding_model)
    ingestion = DocumentIngestionService(
        api_key=api_key,
        config=DocumentIngestionConfig(embedding=embedding_config),
    )
    ingestion_result = ingestion.run()
    if ingestion_result.chunk_count != ingestion.vector_store_service.count():
        pytest.fail("The synchronized RAG index does not contain the expected number of chunks.")

    embedding_service = EmbeddingService(api_key=api_key, config=embedding_config)
    embedding_started = perf_counter()
    query_embeddings = embedding_service.embed_texts([case.question for case in cases])
    query_embedding_seconds = perf_counter() - embedding_started
    if len(query_embeddings) != len(cases):
        pytest.fail("The embedding service did not return one vector per evaluation case.")

    evaluator = RAGEvaluationService()
    summaries: dict[tuple[int, float | None], dict[str, float | int | None]] = {}
    case_results: dict[str, list[tuple[RetrievedChunk, ...]]] = {case.case_id: [] for case in cases}
    for top_k in TOP_K_VALUES:
        for threshold in SIMILARITY_THRESHOLDS:
            results = []
            retrieved_counts = []
            answerable_empty = 0
            unsupported_empty = 0
            for case, query_embedding in zip(cases, query_embeddings, strict=True):
                started = perf_counter()
                matches = ingestion.vector_store_service.search(query_embedding.vector, limit=top_k)
                latency_ms = (perf_counter() - started) * 1000
                ranked_chunks = []
                for match in matches:
                    if match.distance is None:
                        raise ValueError(f"Retrieved chunk {match.chunk_id!r} has no distance.")
                    ranked_chunks.append(RetrievedChunk(chunk=match, score=1.0 - match.distance))

                retrieved = tuple(
                    item for item in ranked_chunks if threshold is None or item.score >= threshold
                )
                if top_k == 5 and threshold == 0.15:
                    case_results[case.case_id].append(retrieved)
                retrieved_counts.append(len(retrieved))
                if not retrieved and case.should_answer:
                    answerable_empty += 1
                elif not retrieved:
                    unsupported_empty += 1
                results.append(evaluator.evaluate_retrieval(case, retrieved, latency_ms=latency_ms))

            summary = evaluator.summarize_retrieval(results)
            summary["retrieved_chunks"] = sum(retrieved_counts) / len(retrieved_counts)
            summary["answerable_empty"] = answerable_empty
            summary["unsupported_empty"] = unsupported_empty
            summaries[(top_k, threshold)] = summary

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = _render_report(
        cases=cases,
        summaries=summaries,
        case_results=case_results,
        corpus_chunks=ingestion_result.chunk_count,
        embedding_model=embedding_config.model,
        query_embedding_seconds=query_embedding_seconds,
        evaluator=evaluator,
    )
    REPORT_PATH.write_text(report, encoding="utf-8")

    assert REPORT_PATH.is_file()
    assert "| `top_k` | Threshold |" in report
    assert all(case.case_id in report for case in cases)
    print(f"RAG evaluation report written to {REPORT_PATH}")
