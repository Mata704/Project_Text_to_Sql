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
    assert all(button.label != "Nova conversa" for button in app.sidebar.button)


def test_about_button_opens_project_info(app) -> None:
    about_button = next(button for button in app.button if button.key == "about_button")
    about_button.click().run()

    assert not app.exception
    assert [s.value for s in app.subheader][-2:] == ["Sumário", "Diagrama"]
    assert any("Pedro Mata" in m.value for m in app.markdown)


def test_first_question_opens_chat_with_answer(app) -> None:
    app.chat_input[0].set_value("olá").run()

    assert not app.exception
    rendered_text = [m.value for m in app.markdown if not m.value.startswith("<style>")]
    assert rendered_text[:2] == ["olá", "resposta a olá"]
    assert app.query_params["session"] == app.session_state["session_id"]
    assert [p.options for p in app.pills] == [["Logs", "Custos", "Evidências"]]
    labels = [b.label for b in app.sidebar.button]
    assert labels == ["Sobre o projeto", "Nova conversa", "olá", "Eliminar"]
    active_style = next(
        element.value
        for element in app.markdown
        if f".st-key-open-session-{app.session_state['session_id']}" in element.value
    )
    assert "rgba(128, 128, 128, 0.14)" in active_style


def test_follow_up_sends_history(app, fake_api) -> None:
    app.chat_input[0].set_value("p1").run()
    app.switch_page("views/chat.py").run()
    app.chat_input[0].set_value("p2").run()

    assert not app.exception
    assert fake_api["calls"][1][0] == "p2"
    assert fake_api["calls"][1][1][0] == {"role": "user", "content": "p1"}


def test_chat_input_disabled_while_waiting(monkeypatch, fake_api) -> None:
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


def test_new_conversation_returns_home_without_creating_or_deleting_session(
    app,
    fake_api,
) -> None:
    app.chat_input[0].set_value("olá").run()
    app.switch_page("views/chat.py").run()
    old_session_id = app.session_state["session_id"]
    next(b for b in app.sidebar.button if b.key == "new-session").click().run()

    assert not app.exception
    assert "session_id" not in app.session_state
    assert [header.value for header in app.header] == ["Pergunte sobre comboios"]
    assert old_session_id in fake_api["sessions"]
    assert not fake_api["deleted"]


def test_session_is_created_only_after_first_question(app, fake_api) -> None:
    assert fake_api["sessions"] == {}

    app.chat_input[0].set_value("primeira pergunta").run()

    session_id = app.session_state["session_id"]
    messages = fake_api["sessions"][session_id]
    assert messages[0] == {"role": "user", "content": "primeira pergunta"}
    assert len(fake_api["sessions"]) == 1


def test_sidebar_deletes_selected_session(app, fake_api) -> None:
    app.chat_input[0].set_value("olá").run()
    app.switch_page("views/chat.py").run()
    session_id = app.session_state["session_id"]
    delete_button = next(
        button for button in app.sidebar.button if button.key == f"delete-session-{session_id}"
    )

    delete_button.click().run()

    assert not app.exception
    assert session_id not in fake_api["sessions"]
    assert session_id in fake_api["deleted"]


def test_home_sidebar_can_open_existing_session(app, fake_api) -> None:
    session_id = sessions.start_session("pergunta guardada")
    app.run()
    open_button = next(
        button for button in app.sidebar.button if button.key == f"open-session-{session_id}"
    )

    open_button.click().run()

    assert not app.exception
    assert app.session_state["session_id"] == session_id
    assert app.query_params["session"] == session_id


def test_error_response_is_displayed(app, monkeypatch) -> None:
    import api_client

    def fail_answer(_session_id):
        raise api_client.ApiClientError("API em baixo")

    monkeypatch.setattr(
        api_client,
        "answer_session",
        fail_answer,
    )
    app.chat_input[0].set_value("olá").run()

    assert [e.value for e in app.error] == ["API em baixo"]
