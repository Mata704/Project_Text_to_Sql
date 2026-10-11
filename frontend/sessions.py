from uuid import uuid4

import streamlit as st

import api_client


@st.cache_resource
def _store() -> dict[str, list[dict]]:
    """Server-side conversations keyed by session id (survive page reloads)."""
    return {}


def get_messages(session_id: str) -> list[dict] | None:
    return _store().get(session_id)


def start_session(question: str) -> str:
    session_id = str(uuid4())
    _store()[session_id] = [{"role": "user", "content": question}]
    return session_id


def add_question(session_id: str, question: str) -> None:
    _store()[session_id].append({"role": "user", "content": question})


def is_pending(messages: list[dict]) -> bool:
    """A conversation awaits the API whenever its last message is the user's."""
    return bool(messages) and messages[-1]["role"] == "user"


def _history(messages: list[dict], limit: int = 10) -> list[dict[str, str]]:
    history = []
    for message in messages:
        if message["role"] == "user":
            history.append({"role": "user", "content": message["content"]})
        elif message["data"].get("answer"):
            history.append({"role": "assistant", "content": message["data"]["answer"]})
    return history[-limit:]


def answer_pending(session_id: str) -> None:
    messages = _store()[session_id]
    result = api_client.ask(messages[-1]["content"], _history(messages[:-1]))
    messages.append({"role": "assistant", "data": result})
