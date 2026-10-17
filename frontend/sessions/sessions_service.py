from typing import Any

import api_client
from constants import ROLE_USER


def get_messages(session_id: str) -> list[dict[str, Any]] | None:
    session = api_client.get_session(session_id)
    return session["messages"] if session is not None else None


def start_session(question: str | None = None) -> str:
    session = api_client.create_session(question)
    session_id = session.get("sessionId")
    if not isinstance(session_id, str) or not session_id:
        raise api_client.ApiClientError("A API não devolveu um identificador de sessão válido.")
    return session_id


def list_sessions() -> list[dict[str, Any]]:
    return api_client.list_sessions()


def add_question(session_id: str, question: str) -> None:
    api_client.add_session_question(session_id, question)


def is_pending(messages: list[dict[str, Any]] | None) -> bool:
    """A conversation awaits the API whenever its last message is the user's."""
    return bool(messages) and messages[-1]["role"] == ROLE_USER


def answer_pending(session_id: str) -> None:
    api_client.answer_session(session_id)


def delete_session(session_id: str) -> None:
    api_client.delete_session(session_id)
