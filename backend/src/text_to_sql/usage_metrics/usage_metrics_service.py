from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import TypedDict
from uuid import uuid4


class _AggregateReport(TypedDict):
    calls: int
    failed_calls: int
    usage_missing_calls: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_seconds: float
    known_cost_usd: float
    estimated_cost_usd: float | None
    unpriced_calls: int


class _ComponentReport(_AggregateReport):
    models: dict[str, _AggregateReport]


class UsageMetricsReport(TypedDict):
    session_id: str
    components: dict[str, _ComponentReport]
    total: _AggregateReport


_PRICES_PER_MILLION_TOKENS: dict[str, tuple[float, float]] = {
    "gpt-4.1-mini": (0.40, 1.60),
    "text-embedding-3-small": (0.02, 0.0),
}


def _prices_for(model: str) -> tuple[float, float] | None:
    """Resolves dated snapshots such as gpt-4.1-mini-2025-04-14 to their base model."""
    if model in _PRICES_PER_MILLION_TOKENS:
        return _PRICES_PER_MILLION_TOKENS[model]
    for base in sorted(_PRICES_PER_MILLION_TOKENS, key=len, reverse=True):
        if model.startswith(f"{base}-"):
            return _PRICES_PER_MILLION_TOKENS[base]
    return None


@dataclass
class _UsageAggregate:
    calls: int = 0
    failed_calls: int = 0
    usage_missing_calls: int = 0
    unpriced_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0
    known_cost_usd: float = 0.0
    models: dict[str, _UsageAggregate] = field(default_factory=dict)

    def add(
        self,
        *,
        model: str,
        usage: object | None,
        elapsed_seconds: float,
        succeeded: bool,
    ) -> None:
        self.calls += 1
        self.failed_calls += not succeeded
        self.latency_seconds += elapsed_seconds

        if usage is None:
            self.usage_missing_calls += 1
            self.unpriced_calls += 1
            return

        input_tokens = _token_count(usage, "input_tokens", "prompt_tokens")
        output_tokens = _token_count(usage, "output_tokens", default=0)
        total_tokens = _token_count(usage, "total_tokens")
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens

        if input_tokens is None or output_tokens is None or total_tokens is None:
            self.usage_missing_calls += 1
            self.unpriced_calls += 1
            return

        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens += total_tokens

        prices = _prices_for(model)
        if prices is None:
            self.unpriced_calls += 1
        else:
            input_price, output_price = prices
            self.known_cost_usd += (
                input_tokens * input_price + output_tokens * output_price
            ) / 1_000_000

    def as_dict(self) -> _AggregateReport:
        return {
            "calls": self.calls,
            "failed_calls": self.failed_calls,
            "usage_missing_calls": self.usage_missing_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "latency_seconds": round(self.latency_seconds, 3),
            "known_cost_usd": round(self.known_cost_usd, 8),
            "estimated_cost_usd": (None if self.unpriced_calls else round(self.known_cost_usd, 8)),
            "unpriced_calls": self.unpriced_calls,
        }


class UsageMetricsService:
    """Accumulates API usage across all calls in one CLI interaction."""

    def __init__(self, session_id: str | None = None) -> None:
        if session_id is not None and not session_id.strip():
            raise ValueError("The usage metrics session ID cannot be empty.")
        self.session_id = session_id or str(uuid4())
        self._components: dict[str, _UsageAggregate] = {}
        self._total = _UsageAggregate()

    def record_call(
        self,
        *,
        component: str,
        model: str,
        usage: object | None,
        elapsed_seconds: float,
        succeeded: bool = True,
    ) -> None:
        if not component.strip():
            raise ValueError("The usage metrics component cannot be empty.")
        if not model.strip():
            raise ValueError("The usage metrics model cannot be empty.")
        if not isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("The API call duration must be finite and non-negative.")

        service_metrics = self._components.setdefault(component, _UsageAggregate())
        model_metrics = service_metrics.models.setdefault(model, _UsageAggregate())
        for aggregate in (service_metrics, model_metrics, self._total):
            aggregate.add(
                model=model,
                usage=usage,
                elapsed_seconds=elapsed_seconds,
                succeeded=succeeded,
            )

    def snapshot(self) -> UsageMetricsReport:
        return {
            "session_id": self.session_id,
            "components": {
                component: {
                    **aggregate.as_dict(),
                    "models": {
                        model: model_aggregate.as_dict()
                        for model, model_aggregate in sorted(aggregate.models.items())
                    },
                }
                for component, aggregate in sorted(self._components.items())
            },
            "total": self._total.as_dict(),
        }


def _token_count(usage: object, *names: str, default: int | None = None) -> int | None:
    for name in names:
        value = getattr(usage, name, None)
        if isinstance(value, int) and value >= 0:
            return value
    return default
