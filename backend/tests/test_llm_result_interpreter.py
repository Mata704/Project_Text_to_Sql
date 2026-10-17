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
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMResultInterpreterService(api_key="test-key", model="test-model")

    answer = service.interpret(
        [
            {
                "question": "Quantas viagens existem?",
                "rows": [{"total_viagens": 42}],
                "failure": None,
            }
        ]
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
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMResultInterpreterService(api_key="test-key")

    answer = service.interpret([{"question": "Que comboios existem?", "rows": [], "failure": None}])

    assert answer == "Não foram encontrados registos."
    assert "[]" in mock_client.responses.parse.call_args.kwargs["input"][0]["content"]


def test_result_interpreter_combines_successful_results_and_partial_failures() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(
        output_parsed={"answer": "Foram encontradas 42 viagens; a outra parte não foi possível."}
    )
    with patch("text_to_sql.llms.common.OpenAI", return_value=mock_client):
        service = LLMResultInterpreterService(api_key="test-key")

    results = [
        {
            "question": "Quantas viagens foram realizadas?",
            "rows": [{"total_viagens": 42}],
            "failure": None,
        },
        {
            "question": "Qual o atraso médio?",
            "rows": [],
            "failure": "Não foi possível gerar uma query.",
        },
    ]
    answer = service.interpret(results)

    assert answer == "Foram encontradas 42 viagens; a outra parte não foi possível."
    assert mock_client.responses.parse.call_count == 1
    prompt = mock_client.responses.parse.call_args.kwargs["input"][0]["content"]
    assert "Quantas viagens foram realizadas?" in prompt
    assert "total_viagens" in prompt
    assert "Qual o atraso médio?" in prompt
    assert "Não foi possível gerar uma query." in prompt


def test_result_interpreter_rejects_empty_results() -> None:
    with patch("text_to_sql.llms.common.OpenAI"):
        service = LLMResultInterpreterService(api_key="test-key")

    with pytest.raises(ValueError, match="At least one question result"):
        service.interpret([])


def test_result_interpreter_rejects_missing_structured_response() -> None:
    mock_client = Mock()
    mock_client.responses.parse.return_value = Mock(output_parsed=None)
    with patch(
        "text_to_sql.llms.common.OpenAI",
        return_value=mock_client,
    ):
        service = LLMResultInterpreterService(api_key="test-key")

    with pytest.raises(LLMError, match="did not return a structured"):
        service.interpret([{"question": "Pergunta?", "rows": [], "failure": None}])


def test_result_interpretation_requires_nonempty_answer() -> None:
    with pytest.raises(ValidationError):
        ResultInterpretation(answer=" ")
