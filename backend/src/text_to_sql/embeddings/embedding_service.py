from collections.abc import Sequence
from time import perf_counter

from openai import OpenAI, OpenAIError
from pydantic import ValidationError

from text_to_sql.constants import (
    COMPONENT_EMBEDDINGS,
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT_SECONDS,
)
from text_to_sql.embeddings.embedding_model import EmbeddingConfig, TextEmbedding
from text_to_sql.errors import EmbeddingError
from text_to_sql.usage_metrics import UsageMetricsService


class EmbeddingService:
    def __init__(
        self,
        api_key: str,
        config: EmbeddingConfig | None = None,
        *,
        usage_metrics: UsageMetricsService | None = None,
        usage_component: str = COMPONENT_EMBEDDINGS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("The OpenAI API key cannot be empty.")

        self.config = config or EmbeddingConfig()
        self.usage_metrics = usage_metrics
        self.usage_component = usage_component
        try:
            self.client = OpenAI(
                api_key=api_key,
                timeout=OPENAI_TIMEOUT_SECONDS,
                max_retries=OPENAI_MAX_RETRIES,
            )
        except OpenAIError as error:
            raise EmbeddingError(f"Could not initialize the OpenAI client: {error}") from error

    def embed_texts(self, texts: Sequence[str]) -> list[TextEmbedding]:
        normalized_texts = self._validate_texts(texts)
        if not normalized_texts:
            return []

        embeddings: list[TextEmbedding] = []
        for batch_start in range(0, len(normalized_texts), self.config.batch_size):
            batch = normalized_texts[batch_start : batch_start + self.config.batch_size]
            embeddings.extend(self._embed_batch(batch, batch_start))
        return embeddings

    def _validate_texts(self, texts: Sequence[str]) -> list[str]:
        if isinstance(texts, str):
            raise ValueError("texts must be a sequence of strings, not a single string.")

        normalized_texts: list[str] = []
        for index, text in enumerate(texts):
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"Text at index {index} must be a non-empty string.")
            normalized_texts.append(text.strip())
        return normalized_texts

    def _embed_batch(self, texts: Sequence[str], batch_start: int) -> list[TextEmbedding]:
        request: dict[str, str | Sequence[str] | int] = {
            "model": self.config.model,
            "input": texts,
        }
        if self.config.dimensions is not None:
            request["dimensions"] = self.config.dimensions

        started_at = perf_counter()
        try:
            response = self.client.embeddings.create(**request)
        except OpenAIError as error:
            if self.usage_metrics is not None:
                self.usage_metrics.record_call(
                    component=self.usage_component,
                    model=self.config.model,
                    usage=None,
                    elapsed_seconds=perf_counter() - started_at,
                    succeeded=False,
                )
            raise EmbeddingError(f"OpenAI could not create text embeddings: {error}") from error
        if self.usage_metrics is not None:
            self.usage_metrics.record_call(
                component=self.usage_component,
                model=response.model or self.config.model,
                usage=response.usage,
                elapsed_seconds=perf_counter() - started_at,
            )

        response_items = sorted(response.data, key=lambda item: item.index)
        if len(response_items) != len(texts):
            raise EmbeddingError(
                "OpenAI returned an unexpected number of embeddings "
                f"({len(response_items)} for {len(texts)} inputs)."
            )

        batch_results: list[TextEmbedding] = []
        for local_index, item in enumerate(response_items):
            if item.index != local_index:
                raise EmbeddingError("OpenAI returned invalid or duplicate embedding indexes.")
            if self.config.dimensions is not None and len(item.embedding) != self.config.dimensions:
                raise EmbeddingError(
                    "OpenAI returned an embedding with an unexpected number of dimensions."
                )
            try:
                batch_results.append(
                    TextEmbedding(
                        text=texts[local_index],
                        vector=item.embedding,
                        model=response.model,
                        index=batch_start + local_index,
                    )
                )
            except ValidationError as error:
                raise EmbeddingError(f"OpenAI returned an invalid embedding: {error}") from error
        return batch_results
