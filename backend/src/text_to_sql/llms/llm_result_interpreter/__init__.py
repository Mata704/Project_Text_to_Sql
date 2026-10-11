"""Natural-language interpretation of SQL query results."""

from text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_model import (
    ResultInterpretation,
)
from text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_service import (
    LLMResultInterpreterService,
)

__all__ = ["LLMResultInterpreterService", "ResultInterpretation"]
