from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuestionResult(TypedDict):
    question: str
    rows: list[dict[str, object]]
    failure: str | None


class ResultInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer: str = Field(min_length=1)

    @field_validator("answer", mode="before")
    @classmethod
    def trim_answer(cls, answer: str) -> str:
        return answer.strip()
