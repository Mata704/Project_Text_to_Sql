from copy import deepcopy
from uuid import uuid4

import pytest


@pytest.fixture
def fake_api(monkeypatch):
    """Replaces the backend session API with a file-store-shaped test double."""
    import api_client

    sessions: dict[str, list[dict]] = {}
    calls: list[tuple[str, list[dict]]] = []
    deleted: list[str] = []

    def create_session(question=None):
        session_id = str(uuid4())
        sessions[session_id] = (
            [{"role": "user", "content": question}] if question is not None else []
        )
        return {"sessionId": session_id, "messages": deepcopy(sessions[session_id])}

    def list_sessions():
        return [
            {
                "sessionId": session_id,
                "title": next(
                    (message["content"] for message in messages if message["role"] == "user"),
                    "Nova conversa",
                ),
                "updatedAt": "2026-10-17T00:00:00+00:00",
            }
            for session_id, messages in sessions.items()
        ]

    def get_session(session_id):
        if session_id not in sessions:
            return None
        return {"sessionId": session_id, "messages": deepcopy(sessions[session_id])}

    def add_session_question(session_id, question):
        sessions[session_id].append({"role": "user", "content": question})
        return {"sessionId": session_id, "messages": deepcopy(sessions[session_id])}

    def answer_session(session_id):
        messages = sessions[session_id]
        question = messages[-1]["content"]
        history = [
            {"role": message["role"], "content": message["content"]}
            if message["role"] == "user"
            else {"role": "assistant", "content": message["data"]["answer"]}
            for message in messages[:-1]
            if message["role"] == "user" or message["data"].get("answer")
        ]
        calls.append((question, history))
        result = {
            "sessionId": session_id,
            "answer": f"resposta a {question}",
            "evidence": [],
            "logs": [],
            "usageMetrics": None,
            "error": None,
        }
        messages.append({"role": "assistant", "data": result})
        return result

    def delete_session(session_id):
        sessions.pop(session_id, None)
        deleted.append(session_id)

    monkeypatch.setattr(api_client, "create_session", create_session)
    monkeypatch.setattr(api_client, "list_sessions", list_sessions)
    monkeypatch.setattr(api_client, "get_session", get_session)
    monkeypatch.setattr(api_client, "add_session_question", add_session_question)
    monkeypatch.setattr(api_client, "answer_session", answer_session)
    monkeypatch.setattr(api_client, "delete_session", delete_session)
    return {
        "calls": calls,
        "deleted": deleted,
        "sessions": sessions,
    }
