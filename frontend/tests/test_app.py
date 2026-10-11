from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import sessions

APP = str(Path(__file__).parent.parent / "app.py")


@pytest.fixture
def app(fake_api):
    return AppTest.from_file(APP, default_timeout=30).run()


def test_home_page_renders(app) -> None:
    assert not app.exception
    assert [h.value for h in app.header] == ["Pergunte sobre comboios"]
    assert len(app.chat_input) == 1


def test_first_question_opens_chat_with_answer(app) -> None:
    app.chat_input[0].set_value("olá").run()

    assert not app.exception
    assert [m.value for m in app.markdown][:2] == ["olá", "resposta a olá"]
    assert app.query_params["session"] == app.session_state["session_id"]
    assert [p.options for p in app.pills] == [["Logs", "Custos", "Evidências"]]
    assert [b.label for b in app.sidebar.button] == ["Nova conversa"]


def test_follow_up_sends_history(app, fake_api) -> None:
    app.chat_input[0].set_value("p1").run()
    app.switch_page("views/chat.py").run()
    app.chat_input[0].set_value("p2").run()

    assert not app.exception
    assert fake_api[1][0] == "p2"
    assert fake_api[1][1][0] == {"role": "user", "content": "p1"}


def test_chat_input_disabled_while_waiting(monkeypatch) -> None:
    def never_answers(_session_id):
        raise TimeoutError("API sem resposta")

    monkeypatch.setattr(sessions, "answer_pending", never_answers)
    session_id = sessions.start_session("pendente")
    at = AppTest.from_file(APP, default_timeout=30)
    at.session_state["session_id"] = session_id
    at.switch_page("views/chat.py").run()

    assert at.chat_input[0].disabled


def test_unknown_session_shows_warning(app) -> None:
    app.query_params["session"] = "inexistente"
    app.switch_page("views/chat.py").run()

    assert [w.value for w in app.warning] == ["Sessão não encontrada."]


def test_new_conversation_returns_home(app) -> None:
    app.chat_input[0].set_value("olá").run()
    app.switch_page("views/chat.py").run()
    app.sidebar.button[0].click().run()

    assert not app.exception
    assert "session_id" not in app.session_state
    assert [h.value for h in app.header] == ["Pergunte sobre comboios"]


def test_error_response_is_displayed(app, monkeypatch) -> None:
    import api_client

    monkeypatch.setattr(api_client, "ask", lambda q, h=None: {"error": "API em baixo"})
    app.chat_input[0].set_value("olá").run()

    assert [e.value for e in app.error] == ["API em baixo"]
