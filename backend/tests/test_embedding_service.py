from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from openai import OpenAIError
from pydantic import ValidationError

from text_to_sql.embeddings import EmbeddingConfig, EmbeddingService, TextEmbedding
from text_to_sql.errors import EmbeddingError
from text_to_sql.usage_metrics import UsageMetricsService


def test_embedding_service_embeds_texts_in_batches_and_keeps_input_order() -> None:
    mock_client = Mock()
    mock_client.embeddings.create.side_effect = [
        Mock(
            model="text-embedding-3-small",
            data=[
                Mock(index=1, embedding=[0.2, 0.3]),
                Mock(index=0, embedding=[0.1, 0.2]),
            ],
        ),
        Mock(
            model="text-embedding-3-small",
            data=[Mock(index=0, embedding=[0.4, 0.5])],
        ),
    ]

    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(
            api_key="test-key",
            config=EmbeddingConfig(batch_size=2, dimensions=2),
        )

    results = service.embed_texts([" chunk one ", "chunk two", "query text"])

    assert [result.text for result in results] == ["chunk one", "chunk two", "query text"]
    assert [result.vector for result in results] == [
        [0.1, 0.2],
        [0.2, 0.3],
        [0.4, 0.5],
    ]
    assert [result.index for result in results] == [0, 1, 2]
    assert all(result.model == "text-embedding-3-small" for result in results)
    assert mock_client.embeddings.create.call_count == 2
    mock_client.embeddings.create.assert_any_call(
        model="text-embedding-3-small",
        input=["chunk one", "chunk two"],
        dimensions=2,
    )
    mock_client.embeddings.create.assert_any_call(
        model="text-embedding-3-small",
        input=["query text"],
        dimensions=2,
    )


def test_embedding_service_uses_default_embedding_model() -> None:
    mock_client = Mock()
    mock_client.embeddings.create.return_value = Mock(
        model="text-embedding-3-small",
        data=[Mock(index=0, embedding=[0.1, 0.2])],
    )

    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(api_key="test-key")

    service.embed_texts(["pergunta"])

    mock_client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input=["pergunta"],
    )


def test_embedding_service_records_usage_for_each_batch() -> None:
    mock_client = Mock()
    mock_client.embeddings.create.return_value = Mock(
        model="text-embedding-3-small",
        data=[Mock(index=0, embedding=[0.1, 0.2])],
        usage=SimpleNamespace(prompt_tokens=12, total_tokens=12),
    )
    metrics = UsageMetricsService()

    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(
            api_key="test-key",
            usage_metrics=metrics,
            usage_component="query_embeddings",
        )

    service.embed_texts(["pergunta"])

    component_metrics = metrics.snapshot()["components"]["query_embeddings"]
    assert component_metrics["calls"] == 1
    assert component_metrics["input_tokens"] == 12
    assert component_metrics["output_tokens"] == 0
    assert component_metrics["total_tokens"] == 12
    assert component_metrics["unpriced_calls"] == 0
    assert component_metrics["estimated_cost_usd"] == pytest.approx(12 * 0.02 / 1_000_000)


def test_embedding_service_returns_empty_list_without_api_call() -> None:
    mock_client = Mock()
    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(api_key="test-key")

    assert service.embed_texts([]) == []
    mock_client.embeddings.create.assert_not_called()


def test_embedding_service_rejects_blank_input_and_api_key() -> None:
    with pytest.raises(ValueError, match="API key cannot be empty"):
        EmbeddingService(api_key=" ")

    with patch("text_to_sql.embeddings.embedding_service.OpenAI", return_value=Mock()):
        service = EmbeddingService(api_key="test-key")

    with pytest.raises(ValueError, match="index 1"):
        service.embed_texts(["valid", " \n"])
    with pytest.raises(ValueError, match="not a single string"):
        service.embed_texts("uma pergunta")


def test_embedding_service_reports_incomplete_api_response() -> None:
    mock_client = Mock()
    mock_client.embeddings.create.return_value = Mock(
        model="text-embedding-3-small",
        data=[],
    )
    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(api_key="test-key")

    with pytest.raises(EmbeddingError, match="unexpected number"):
        service.embed_texts(["pergunta"])


def test_embedding_service_reports_invalid_response_index() -> None:
    mock_client = Mock()
    mock_client.embeddings.create.return_value = Mock(
        model="text-embedding-3-small",
        data=[Mock(index=1, embedding=[0.1])],
    )
    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(api_key="test-key")

    with pytest.raises(EmbeddingError, match="invalid or duplicate"):
        service.embed_texts(["pergunta"])


def test_embedding_service_reports_openai_errors() -> None:
    mock_client = Mock()
    mock_client.embeddings.create.side_effect = OpenAIError("provider failure")
    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(api_key="test-key")

    with pytest.raises(EmbeddingError, match="could not create text embeddings"):
        service.embed_texts(["pergunta"])


def test_embedding_service_reports_unexpected_embedding_dimensions() -> None:
    mock_client = Mock()
    mock_client.embeddings.create.return_value = Mock(
        model="text-embedding-3-small",
        data=[Mock(index=0, embedding=[0.1])],
    )
    with patch(
        "text_to_sql.embeddings.embedding_service.OpenAI",
        return_value=mock_client,
    ):
        service = EmbeddingService(
            api_key="test-key",
            config=EmbeddingConfig(dimensions=2),
        )

    with pytest.raises(EmbeddingError, match="unexpected number of dimensions"):
        service.embed_texts(["pergunta"])


def test_embedding_config_and_vector_reject_invalid_values() -> None:
    with pytest.raises(ValidationError, match="batch_size"):
        EmbeddingConfig(batch_size=0)

    with pytest.raises(ValidationError, match="finite"):
        TextEmbedding(
            text="texto",
            vector=[float("inf")],
            model="text-embedding-3-small",
            index=0,
        )
