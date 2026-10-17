import os
from typing import Any

import requests

from api_client.constants import (
    API_BASE_URL_ENV,
    CHAT_PATH,
    DEFAULT_API_BASE_URL,
    REQUEST_TIMEOUT_SECONDS,
)

API_BASE_URL = os.environ.get(API_BASE_URL_ENV, DEFAULT_API_BASE_URL).rstrip("/")


class ApiClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    allow_error_response: bool = False,
    not_found_ok: bool = False,
) -> Any:
    try:
        response = requests.request(
            method,
            f"{API_BASE_URL}{path}",
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise ApiClientError(f"Não foi possível contactar a API: {exc}") from exc
    if not_found_ok and response.status_code == 404:
        return None
    if response.status_code == 204:
        return None
    try:
        data = response.json()
    except ValueError as exc:
        raise ApiClientError(
            f"Resposta inválida da API (HTTP {response.status_code}).",
            response.status_code,
        ) from exc
    if response.status_code >= 400 and not (
        allow_error_response and isinstance(data, dict) and "sessionId" in data
    ):
        detail = data.get("detail") if isinstance(data, dict) else None
        message = f"Erro HTTP {response.status_code}"
        if detail:
            message = f"{message}: {detail}"
        raise ApiClientError(message, response.status_code)
    return data


def create_session(question: str | None = None) -> dict[str, Any]:
    payload = {"question": question} if question is not None else {}
    return _request("POST", "/sessions", payload)


def list_sessions() -> list[dict[str, Any]]:
    return _request("GET", "/sessions")


def get_session(session_id: str) -> dict[str, Any] | None:
    return _request("GET", f"/sessions/{session_id}", not_found_ok=True)


def add_session_question(session_id: str, question: str) -> dict[str, Any]:
    return _request(
        "POST",
        f"/sessions/{session_id}/questions",
        {"question": question},
    )


def answer_session(session_id: str) -> dict[str, Any]:
    return _request(
        "POST",
        f"/sessions/{session_id}/answer",
        allow_error_response=True,
    )


def delete_session(session_id: str) -> None:
    _request("DELETE", f"/sessions/{session_id}")


def ask(question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Calls POST /chat and always returns a response-shaped dict."""
    try:
        response = requests.post(
            f"{API_BASE_URL}{CHAT_PATH}",
            json={"question": question, "history": history or []},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        return {"error": f"Não foi possível contactar a API: {exc}"}
    try:
        data = response.json()
    except ValueError:
        return {"error": f"Resposta inválida da API (HTTP {response.status_code})."}
    if response.status_code >= 400 and not isinstance(data, dict | list):
        return {"error": f"Erro HTTP {response.status_code}."}
    if isinstance(data, dict) and "detail" in data and "sessionId" not in data:
        return {"error": f"Pedido inválido: {data['detail']}"}
    return data
