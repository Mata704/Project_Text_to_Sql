from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConversationMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class QuestionClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["relevant", "irrelevant", "ambiguous"]
    normalized_query: str = Field(min_length=1)
    clarification_question: str | None = None

    @model_validator(mode="after")
    def validate_clarification(self) -> QuestionClassificationResult:
        self.normalized_query = self.normalized_query.strip()
        if not self.normalized_query:
            raise ValueError("The normalized query cannot be empty.")
        if self.status == "ambiguous":
            if not self.clarification_question or not self.clarification_question.strip():
                raise ValueError("Ambiguous questions require a clarification question.")
            self.clarification_question = self.clarification_question.strip()
        elif self.clarification_question is not None:
            raise ValueError("Only ambiguous questions may include a clarification question.")
        return self
