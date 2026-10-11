from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from text_to_sql.api.chat import ChatRuntime, answer_chat, prepare_runtime
from text_to_sql.interaction_logs import InteractionResponse
from text_to_sql.llms.llm_selector import ConversationMessage


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
    status: str = "ok"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.runtime = prepare_runtime()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Text-to-SQL Comboios", lifespan=lifespan)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse()

    @app.post("/chat", response_model=InteractionResponse)
    def chat(payload: ChatRequest, request: Request, response: Response) -> InteractionResponse:
        runtime: ChatRuntime = request.app.state.runtime
        result = answer_chat(payload.question, runtime, payload.history)
        if result.error is not None:
            response.status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        return result

    return app


app = create_app()
