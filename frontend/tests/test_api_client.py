import requests

import api_client


class _Response:
    def __init__(self, status_code=200, payload=None, invalid_json=False):
        self.status_code = status_code
        self._payload = payload
        self._invalid_json = invalid_json

    def json(self):
        if self._invalid_json:
            raise ValueError("no json")
        return self._payload


def test_ask_sends_question_and_history(monkeypatch) -> None:
    sent = {}

    def fake_post(url, json, timeout):
        sent.update(url=url, json=json)
        return _Response(payload={"sessionId": "s", "answer": "ok"})

    monkeypatch.setattr(requests, "post", fake_post)
    history = [{"role": "user", "content": "oi"}]

    result = api_client.ask("pergunta", history)

    assert result["answer"] == "ok"
    assert sent["url"].endswith("/chat")
    assert sent["json"] == {"question": "pergunta", "history": history}


def test_ask_defaults_to_empty_history(monkeypatch) -> None:
    sent = {}
    monkeypatch.setattr(
        requests,
        "post",
        lambda url, json, timeout: sent.update(json=json) or _Response(payload={}),
    )
    api_client.ask("pergunta")
    assert sent["json"]["history"] == []


def test_ask_returns_error_when_api_unreachable(monkeypatch) -> None:
    def fail(*_args, **_kwargs):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(requests, "post", fail)
    assert "Não foi possível contactar a API" in api_client.ask("x")["error"]


def test_ask_returns_error_for_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: _Response(status_code=502, invalid_json=True),
    )
    assert "502" in api_client.ask("x")["error"]


def test_ask_reports_validation_detail(monkeypatch) -> None:
    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: _Response(status_code=422, payload={"detail": "campo em falta"}),
    )
    assert "campo em falta" in api_client.ask("x")["error"]


def test_ask_keeps_api_error_payload(monkeypatch) -> None:
    payload = {"sessionId": "s", "answer": None, "error": "falhou"}
    monkeypatch.setattr(
        requests, "post", lambda *a, **k: _Response(status_code=422, payload=payload)
    )
    assert api_client.ask("x") == payload


def test_create_empty_session_sends_empty_payload(monkeypatch) -> None:
    sent = {}
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, json, timeout: (
            sent.update(
                method=method,
                url=url,
                json=json,
            )
            or _Response(status_code=201, payload={"sessionId": "s", "messages": []})
        ),
    )

    result = api_client.create_session()

    assert result["messages"] == []
    assert sent["method"] == "POST"
    assert sent["url"].endswith("/sessions")
    assert sent["json"] == {}


def test_list_sessions_gets_backend_session_list(monkeypatch) -> None:
    expected = [{"sessionId": "s", "title": "pergunta", "updatedAt": "now"}]
    sent = {}
    monkeypatch.setattr(
        requests,
        "request",
        lambda method, url, json, timeout: (
            sent.update(method=method, url=url) or _Response(payload=expected)
        ),
    )

    assert api_client.list_sessions() == expected
    assert sent == {"method": "GET", "url": f"{api_client.API_BASE_URL}/sessions"}
