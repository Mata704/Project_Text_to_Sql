from unittest.mock import Mock

import pytest

from text_to_sql import __main__ as app_main


@pytest.mark.parametrize(("configured_port", "expected_port"), [(None, 8000), ("8001", 8001)])
def test_main_uses_configured_port(
    monkeypatch,
    configured_port: str | None,
    expected_port: int,
) -> None:
    run = Mock()
    monkeypatch.setattr(app_main.uvicorn, "run", run)
    if configured_port is None:
        monkeypatch.delenv("TEXT_TO_SQL_PORT", raising=False)
    else:
        monkeypatch.setenv("TEXT_TO_SQL_PORT", configured_port)

    app_main.main()

    run.assert_called_once_with("text_to_sql.api:app", host="127.0.0.1", port=expected_port)


def test_main_rejects_invalid_port(monkeypatch) -> None:
    run = Mock()
    monkeypatch.setattr(app_main.uvicorn, "run", run)
    monkeypatch.setenv("TEXT_TO_SQL_PORT", "invalid")

    with pytest.raises(ValueError):
        app_main.main()

    run.assert_not_called()
