from uuid import uuid4

import streamlit as st

import api_client
from constants import ROLE_ASSISTANT, ROLE_USER
from sessions.constants import HISTORY_MESSAGES_LIMIT


@st.cache_resource
def _store() -> dict[str, list[dict]]:
    """Server-side conversations keyed by session id (survive page reloads)."""
    return {}


def get_messages(session_id: str) -> list[dict] | None:
    return _store().get(session_id)


def start_session(question: str) -> str:
    session_id = str(uuid4())
    _store()[session_id] = [{"role": ROLE_USER, "content": question}]
    return session_id


def add_question(session_id: str, question: str) -> None:
    _store()[session_id].append({"role": ROLE_USER, "content": question})


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
    messages.append({"role": ROLE_ASSISTANT, "data": result})
