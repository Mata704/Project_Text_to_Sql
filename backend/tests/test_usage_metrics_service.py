from types import SimpleNamespace

from text_to_sql.usage_metrics import UsageMetricsService


def test_usage_metrics_accumulate_calls_by_component_model_and_session_total() -> None:
    metrics = UsageMetricsService()
    response_usage = SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120)

    metrics.record_call(
        component="sql_generator",
        model="gpt-4.1-mini",
        usage=response_usage,
        elapsed_seconds=0.25,
    )
    metrics.record_call(
        component="sql_generator",
        model="gpt-4.1-mini",
        usage=response_usage,
        elapsed_seconds=0.5,
    )
    metrics.record_call(
        component="result_interpreter",
        model="unknown-model",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15),
        elapsed_seconds=0.1,
    )

    report = metrics.snapshot()

    assert report["session_id"] == metrics.session_id
    assert report["components"]["sql_generator"]["calls"] == 2
    assert report["components"]["sql_generator"]["total_tokens"] == 240
    assert report["components"]["sql_generator"]["estimated_cost_usd"] == 0.000144
    assert report["components"]["sql_generator"]["models"]["gpt-4.1-mini"]["calls"] == 2
    assert report["components"]["result_interpreter"]["unpriced_calls"] == 1
    assert report["components"]["result_interpreter"]["estimated_cost_usd"] is None
    assert report["total"]["calls"] == 3
    assert report["total"]["input_tokens"] == 210
    assert report["total"]["output_tokens"] == 45
    assert report["total"]["total_tokens"] == 255
    assert report["total"]["estimated_cost_usd"] is None


def test_usage_metrics_track_missing_usage_and_failed_calls() -> None:
    metrics = UsageMetricsService()

    metrics.record_call(
        component="question_classifier",
        model="gpt-4.1-mini",
        usage=None,
        elapsed_seconds=0.04,
        succeeded=False,
    )

    classifier_metrics = metrics.snapshot()["components"]["question_classifier"]
    assert classifier_metrics["calls"] == 1
    assert classifier_metrics["failed_calls"] == 1
    assert classifier_metrics["usage_missing_calls"] == 1
    assert classifier_metrics["unpriced_calls"] == 1
