import json

import pytest

from text_to_sql.sessions import (
    MAX_MESSAGES_PER_SESSION,
    SessionConflictError,
    SessionNotFoundError,
    SessionStore,
)


def test_session_is_persisted_in_file_named_by_id(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id, messages = store.create("olá")

    session_file = tmp_path / session_id
    assert session_file.is_file()
    assert session_file.suffix == ""
    assert json.loads(session_file.read_text(encoding="utf-8")) == messages
    assert SessionStore(tmp_path).get(session_id) == messages


def test_new_session_can_be_created_empty_and_is_listed(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id, messages = store.create()

    assert messages == []
    assert store.get(session_id) == []
    assert store.list_sessions()[0]["session_id"] == session_id
    assert store.list_sessions()[0]["title"] == "Nova conversa"


def test_session_list_uses_first_question_as_title_and_keeps_all_sessions(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_ids = [store.create(f"Pergunta {index}")[0] for index in range(55)]

    listed_ids = [session["session_id"] for session in store.list_sessions()]
    assert set(listed_ids) == set(session_ids)
    assert all(session["title"].startswith("Pergunta ") for session in store.list_sessions())


def test_store_adds_questions_and_answers_to_file(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id, _ = store.create("p1")
    store.add_answer(session_id, {"answer": "r1"})
    store.add_question(session_id, "p2")

    messages = store.get(session_id)
    assert messages == [
        {"role": "user", "content": "p1"},
        {"role": "assistant", "data": {"answer": "r1"}},
        {"role": "user", "content": "p2"},
    ]


def test_store_rejects_duplicate_pending_questions(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id, _ = store.create("p1")

    with pytest.raises(SessionConflictError):
        store.add_question(session_id, "p2")


def test_store_trims_history_to_message_limit(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id, _ = store.create("q0")
    for index in range(1, 31):
        store.add_answer(session_id, {"answer": f"a{index - 1}"})
        store.add_question(session_id, f"q{index}")
    store.add_answer(session_id, {"answer": "a30"})

    messages = store.get(session_id)
    assert len(messages) <= MAX_MESSAGES_PER_SESSION
    assert messages[0]["role"] == "user"
    assert messages[-1]["data"]["answer"] == "a30"
    assert messages[-2]["content"] == "q30"


def test_store_trims_existing_history_over_message_limit(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id, _ = store.create("q0")
    messages = [
        (
            {"role": "user", "content": f"q{index}"}
            if index % 2 == 0
            else {"role": "assistant", "data": {"answer": f"a{index}"}}
        )
        for index in range(60)
    ]
    (tmp_path / session_id).write_text(json.dumps(messages), encoding="utf-8")

    trimmed_messages = store.get(session_id)

    assert len(trimmed_messages) <= MAX_MESSAGES_PER_SESSION
    assert trimmed_messages[0]["role"] == "user"
    assert trimmed_messages[-1]["data"]["answer"] == "a59"
    assert trimmed_messages[0]["content"] == "q10"
    assert json.loads((tmp_path / session_id).read_text(encoding="utf-8")) == trimmed_messages


def test_store_deletes_session_file(tmp_path) -> None:
    store = SessionStore(tmp_path)
    session_id, _ = store.create("olá")

    assert store.delete(session_id)
    assert not (tmp_path / session_id).exists()
    assert not store.delete(session_id)
    with pytest.raises(SessionNotFoundError):
        store.get(session_id)


@pytest.mark.parametrize("session_id", ["../outside", "not-a-uuid"])
def test_store_rejects_invalid_session_ids(tmp_path, session_id: str) -> None:
    with pytest.raises(ValueError):
        SessionStore(tmp_path).get(session_id)
