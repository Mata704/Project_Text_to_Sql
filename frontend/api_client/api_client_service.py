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
