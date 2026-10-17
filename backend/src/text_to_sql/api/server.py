from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from text_to_sql.api.chat import ChatRuntime, answer_chat, prepare_runtime
from text_to_sql.api.constants import APP_TITLE, HEALTH_STATUS_OK
from text_to_sql.interaction_logs import InteractionResponse
from text_to_sql.llms.llm_selector import ConversationMessage
from text_to_sql.sessions import (
    InvalidSessionIdError,
    SessionConflictError,
    SessionNotFoundError,
    SessionStore,
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    history: list[ConversationMessage] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("The question cannot be empty.")
        return value


class HealthResponse(BaseModel):
    status: str = HEALTH_STATUS_OK


class SessionQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("The question cannot be empty.")
        return value


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str | None = None

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("The question cannot be empty.")
        return value


class SessionResponse(BaseModel):
    session_id: str = Field(serialization_alias="sessionId")
    messages: list[dict[str, Any]]


class SessionSummary(BaseModel):
    session_id: str = Field(serialization_alias="sessionId")
    title: str
    updated_at: str = Field(serialization_alias="updatedAt")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.runtime = prepare_runtime()
    yield


def create_app(session_store: SessionStore | None = None) -> FastAPI:
    app = FastAPI(title=APP_TITLE, lifespan=lifespan)
    app.state.session_store = session_store or SessionStore()

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
    def create_session(payload: SessionCreateRequest, request: Request) -> SessionResponse:
        session_id, messages = request.app.state.session_store.create(payload.question)
        return SessionResponse(session_id=session_id, messages=messages)

    @app.get("/sessions", response_model=list[SessionSummary])
    def list_sessions(request: Request) -> list[SessionSummary]:
        return [
            SessionSummary(
                session_id=session["session_id"],
                title=session["title"],
                updated_at=session["updated_at"],
            )
            for session in request.app.state.session_store.list_sessions()
        ]

    @app.get("/sessions/{session_id}", response_model=SessionResponse)
    def get_session(session_id: str, request: Request) -> SessionResponse:
        try:
            messages = request.app.state.session_store.get(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sessão não encontrada.",
            ) from error
        except InvalidSessionIdError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sessão não encontrada.",
            ) from None
        return SessionResponse(session_id=session_id, messages=messages)

    @app.post("/sessions/{session_id}/questions", response_model=SessionResponse)
    def add_session_question(
        session_id: str,
        payload: SessionQuestionRequest,
        request: Request,
    ) -> SessionResponse:
        try:
            messages = request.app.state.session_store.add_question(session_id, payload.question)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sessão não encontrada.",
            ) from error
        except SessionConflictError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except InvalidSessionIdError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return SessionResponse(session_id=session_id, messages=messages)

    @app.post("/sessions/{session_id}/answer", response_model=InteractionResponse)
    def answer_session(
        session_id: str,
        request: Request,
        response: Response,
    ) -> InteractionResponse:
        try:
            messages = request.app.state.session_store.get(session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sessão não encontrada.",
            ) from error
        except InvalidSessionIdError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        if not messages or messages[-1]["role"] != "user":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A sessão não tem uma pergunta pendente.",
            )

        question = messages[-1]["content"]
        history = [
            ConversationMessage(role=message["role"], content=message["content"])
            if message["role"] == "user"
            else ConversationMessage(role="assistant", content=message["data"]["answer"])
            for message in messages[:-1]
            if message["role"] == "user" or message["data"].get("answer")
        ]
        runtime: ChatRuntime = request.app.state.runtime
        result = answer_chat(question, runtime, history, session_id=session_id)
        request.app.state.session_store.add_answer(
            session_id,
            result.model_dump(mode="json", by_alias=True),
        )
        if result.error is not None:
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return result

    @app.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_session(session_id: str, request: Request) -> Response:
        try:
            request.app.state.session_store.delete(session_id)
        except InvalidSessionIdError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @app.post("/chat", response_model=InteractionResponse)
    def chat(payload: ChatRequest, request: Request, response: Response) -> InteractionResponse:
        runtime: ChatRuntime = request.app.state.runtime
        result = answer_chat(payload.question, runtime, payload.history)
        if result.error is not None:
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return result

    return app


app = create_app()
