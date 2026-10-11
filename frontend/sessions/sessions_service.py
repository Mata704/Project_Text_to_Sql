from uuid import uuid4

import streamlit as st

import api_client
from constants import ROLE_ASSISTANT, ROLE_USER
from sessions.constants import HISTORY_MESSAGES_LIMIT, MAX_MESSAGES_PER_SESSION, MAX_STORED_SESSIONS


@st.cache_resource
def _store() -> dict[str, list[dict]]:
    """Server-side conversations keyed by session id (survive page reloads)."""
    return {}


def _evict_oldest_sessions(store: dict[str, list[dict]]) -> None:
    while len(store) > MAX_STORED_SESSIONS:
        del store[next(iter(store))]


def _trim_messages(messages: list[dict]) -> None:
    excess = len(messages) - MAX_MESSAGES_PER_SESSION
    if excess > 0:
        del messages[:excess]
        while messages and messages[0]["role"] != ROLE_USER:
            del messages[0]


def get_messages(session_id: str) -> list[dict] | None:
    store = _store()
    messages = store.pop(session_id, None)
    if messages is not None:
        store[session_id] = messages
    return messages


def start_session(question: str) -> str:
    session_id = str(uuid4())
    store = _store()
    store[session_id] = [{"role": ROLE_USER, "content": question}]
    _evict_oldest_sessions(store)
    return session_id


def add_question(session_id: str, question: str) -> None:
    messages = _store()[session_id]
    messages.append({"role": ROLE_USER, "content": question})
    _trim_messages(messages)


def is_pending(messages: list[dict]) -> bool:
    """A conversation awaits the API whenever its last message is the user's."""
    return bool(messages) and messages[-1]["role"] == ROLE_USER


def _history(messages: list[dict], limit: int = HISTORY_MESSAGES_LIMIT) -> list[dict[str, str]]:
    history = []
    for message in messages:
        if message["role"] == ROLE_USER:
            history.append({"role": ROLE_USER, "content": message["content"]})
        elif message["data"].get("answer"):
            history.append({"role": ROLE_ASSISTANT, "content": message["data"]["answer"]})
    return history[-limit:]


def answer_pending(session_id: str) -> None:
    messages = _store()[session_id]
    result = api_client.ask(messages[-1]["content"], _history(messages[:-1]))
    if not isinstance(result, dict):
        result = {"error": "Resposta inesperada da API."}
    messages.append({"role": ROLE_ASSISTANT, "data": result})
    _trim_messages(messages)
