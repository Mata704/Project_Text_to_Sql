import sessions


def test_start_session_creates_backend_session(fake_api) -> None:
    session_id = sessions.start_session("olá")

    assert sessions.get_messages(session_id) == [{"role": "user", "content": "olá"}]
    assert sessions.is_pending(sessions.get_messages(session_id))


def test_unknown_session_returns_none(fake_api) -> None:
    assert sessions.get_messages("nope") is None


def test_answer_pending_fetches_persisted_messages(fake_api) -> None:
    session_id = sessions.start_session("olá")
    sessions.answer_pending(session_id)

    messages = sessions.get_messages(session_id)
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["data"]["answer"] == "resposta a olá"
    assert not sessions.is_pending(messages)
    assert fake_api["calls"] == [("olá", [])]


def test_history_is_available_to_backend_for_follow_up(fake_api) -> None:
    session_id = sessions.start_session("p1")
    sessions.answer_pending(session_id)
    sessions.add_question(session_id, "p2")
    sessions.answer_pending(session_id)

    assert fake_api["calls"][1] == (
        "p2",
        [
            {"role": "user", "content": "p1"},
            {"role": "assistant", "content": "resposta a p1"},
        ],
    )


def test_backend_session_deletion_removes_current_conversation(fake_api) -> None:
    session_id = sessions.start_session("olá")

    sessions.delete_session(session_id)

    assert session_id not in fake_api["sessions"]
    assert fake_api["deleted"] == [session_id]
