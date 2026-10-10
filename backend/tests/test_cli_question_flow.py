from types import SimpleNamespace

from pydantic import SecretStr

from text_to_sql.cli import main


def test_cli_only_constructs_and_calls_selector_service(monkeypatch) -> None:
    calls: list[tuple[dict[str, str], int]] = []

    class FakeSelectorService:
        def __init__(self, **kwargs: str) -> None:
            self.kwargs = kwargs

        def run(self, question: str) -> None:
            calls.append((self.kwargs, question))

    monkeypatch.setattr(
        "text_to_sql.cli.Settings",
        lambda: SimpleNamespace(
            openai_api_key=SecretStr("test-key"),
            openai_model="test-model",
        ),
    )
    monkeypatch.setattr(
        "text_to_sql.cli.LLMSelectorService",
        FakeSelectorService,
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "Quantas viagens?")

    assert main() == 0
    assert calls == [
        (
            {"api_key": "test-key", "model": "test-model"},
            "Quantas viagens?",
        )
    ]
