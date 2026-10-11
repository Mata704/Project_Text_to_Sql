import os
from typing import Any

import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def ask(question: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Calls POST /chat and always returns a response-shaped dict."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/chat",
            json={"question": question, "history": history or []},
            timeout=180,
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
