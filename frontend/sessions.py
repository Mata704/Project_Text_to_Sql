import streamlit as st

import api_client


@st.cache_resource
def _store() -> dict[str, list[dict]]:
    """Server-side conversations keyed by session id (survive page reloads)."""
    return {}


def get_messages(session_id: str) -> list[dict] | None:
    return _store().get(session_id)


def start_session(question: str) -> str:
    """Sends the first question; the API's sessionId becomes the page's session."""
    result = api_client.ask(question)
    session_id = result.get("sessionId") or f"local-{len(_store()) + 1}"
    _store()[session_id] = [
        {"role": "user", "content": question},
        {"role": "assistant", "data": result},
    ]
    return session_id


def _history(messages: list[dict], limit: int = 10) -> list[dict[str, str]]:
    history = []
    for message in messages:
        if message["role"] == "user":
            history.append({"role": "user", "content": message["content"]})
        elif message["data"].get("answer"):
            history.append({"role": "assistant", "content": message["data"]["answer"]})
    return history[-limit:]


def add_turn(session_id: str, question: str) -> None:
    messages = _store()[session_id]
    result = api_client.ask(question, _history(messages))
    messages.append({"role": "user", "content": question})
    messages.append({"role": "assistant", "data": result})
