from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from text_to_sql.errors import LLMError
from text_to_sql.llms import LLMResultInterpreterService
from text_to_sql.llms.llm_result_interpreter import ResultInterpretation


def test_result_interpreter_answers_original_question_from_rows() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(
        output_parsed={"answer": "Foram encontradas 42 viagens."}
    )
    with patch(
        "text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_service.OpenAI",
        return_value=mock_client,
    ):
        service = LLMResultInterpreterService(api_key="test-key", model="test-model")

    answer = service.interpret(
        "Quantas viagens existem?",
        [{"total_viagens": 42}],
    )

    assert answer == "Foram encontradas 42 viagens."
    call = mock_client.responses.parse.call_args.kwargs
    assert call["model"] == "test-model"
    assert call["text_format"] is ResultInterpretation
    assert "Quantas viagens existem?" in call["input"][0]["content"]
    assert "[{'total_viagens': 42}]" in call["input"][0]["content"]


def test_result_interpreter_passes_empty_rows_to_the_model() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(
        output_parsed={"answer": "Não foram encontrados registos."}
    )
    with patch(
        "text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_service.OpenAI",
        return_value=mock_client,
    ):
        service = LLMResultInterpreterService(api_key="test-key")

    answer = service.interpret("Que comboios existem?", [])

    assert answer == "Não foram encontrados registos."
    assert "[]" in mock_client.responses.parse.call_args.kwargs["input"][0]["content"]


def test_result_interpreter_rejects_empty_question() -> None:
    with patch("text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_service.OpenAI"):
        service = LLMResultInterpreterService(api_key="test-key")

    with pytest.raises(ValueError, match="question cannot be empty"):
        service.interpret("  ", [])


def test_result_interpreter_rejects_missing_structured_response() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(output_parsed=None)
    with patch(
        "text_to_sql.llms.llm_result_interpreter.llm_result_interpreter_service.OpenAI",
        return_value=mock_client,
    ):
        service = LLMResultInterpreterService(api_key="test-key")

    with pytest.raises(LLMError, match="did not return a structured"):
        service.interpret("Pergunta?", [])


def test_result_interpretation_requires_nonempty_answer() -> None:
    with pytest.raises(ValidationError):
        ResultInterpretation(answer=" ")
