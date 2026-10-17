import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

MAX_MESSAGES_PER_SESSION = 50


class SessionNotFoundError(FileNotFoundError):
    pass


class InvalidSessionIdError(ValueError):
    pass


class SessionConflictError(ValueError):
    pass


class SessionStore:
    """Persists each conversation in an extensionless JSON file."""

    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or Path(__file__).resolve().parents[3] / "data" / "sessions"

    def create(self, question: str | None = None) -> tuple[str, list[dict[str, Any]]]:
        session_id = str(uuid4())
        messages: list[dict[str, Any]] = (
            [{"role": "user", "content": question}] if question is not None else []
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        self._write(session_id, messages)
        return session_id, messages

    def get(self, session_id: str) -> list[dict[str, Any]]:
        path = self._path(session_id)
        if not path.is_file():
            raise SessionNotFoundError(session_id)
        messages = json.loads(path.read_text(encoding="utf-8"))
        if len(messages) > MAX_MESSAGES_PER_SESSION:
            self._trim_messages(messages)
            self._write(session_id, messages)
        return messages

    def add_question(self, session_id: str, question: str) -> list[dict[str, Any]]:
        messages = self.get(session_id)
        if messages and messages[-1]["role"] == "user":
            raise SessionConflictError("A sessão já está a aguardar uma resposta.")
        messages.append({"role": "user", "content": question})
        self._trim_messages(messages)
        self._write(session_id, messages)
        return messages

    def add_answer(self, session_id: str, answer: dict[str, Any]) -> list[dict[str, Any]]:
        messages = self.get(session_id)
        if not messages or messages[-1]["role"] != "user":
            raise SessionConflictError("A sessão não tem uma pergunta pendente.")
        messages.append({"role": "assistant", "data": answer})
        self._trim_messages(messages)
        self._write(session_id, messages)
        return messages

    def delete(self, session_id: str) -> bool:
        path = self._path(session_id)
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True

    def list_sessions(self) -> list[dict[str, str]]:
        if not self.directory.exists():
            return []

        sessions: list[tuple[int, dict[str, str]]] = []
        for path in self.directory.iterdir():
            if not path.is_file():
                continue
            session_id = str(UUID(path.name))
            messages = json.loads(path.read_text(encoding="utf-8"))
            title = next(
                (
                    message["content"].strip()
                    for message in messages
                    if message.get("role") == "user" and message.get("content", "").strip()
                ),
                "Nova conversa",
            )
            updated_at = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
            sessions.append(
                (
                    path.stat().st_mtime_ns,
                    {"session_id": session_id, "title": title, "updated_at": updated_at},
                )
            )
        sessions.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in sessions]

    def _path(self, session_id: str) -> Path:
        try:
            canonical_id = str(UUID(session_id))
        except ValueError as error:
            raise InvalidSessionIdError("The session ID must be a UUID.") from error
        return self.directory / canonical_id

    def _write(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path(session_id).write_text(
            json.dumps(messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _trim_messages(messages: list[dict[str, Any]]) -> None:
        excess = len(messages) - MAX_MESSAGES_PER_SESSION
        if excess > 0:
            del messages[:excess]
            while messages and messages[0]["role"] != "user":
                del messages[0]
