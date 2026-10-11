import pytest

from sessions import sessions_service


@pytest.fixture(autouse=True)
def fresh_store(monkeypatch):
    store: dict[str, list[dict]] = {}
    monkeypatch.setattr(sessions_service, "_store", lambda: store)
    return store


@pytest.fixture
def fake_api(monkeypatch):
    """Replaces the API client and records every call."""
    import api_client

    calls: list[tuple[str, list[dict]]] = []

    def fake_ask(question, history=None):
        calls.append((question, history or []))
        return {
            "sessionId": "api-id",
            "answer": f"resposta a {question}",
            "evidence": [],
            "logs": [],
            "usageMetrics": None,
            "error": None,
        }

    monkeypatch.setattr(api_client, "ask", fake_ask)
    return calls
