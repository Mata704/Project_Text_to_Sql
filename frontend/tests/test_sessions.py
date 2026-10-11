import sessions


def test_start_session_stores_pending_question() -> None:
    session_id = sessions.start_session("olá")

    messages = sessions.get_messages(session_id)
    assert messages == [{"role": "user", "content": "olá"}]
    assert sessions.is_pending(messages)


def test_unknown_session_returns_none() -> None:
    assert sessions.get_messages("nope") is None


def test_answer_pending_appends_assistant_message(fake_api) -> None:
    session_id = sessions.start_session("olá")
    sessions.answer_pending(session_id)

    messages = sessions.get_messages(session_id)
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["data"]["answer"] == "resposta a olá"
    assert not sessions.is_pending(messages)
    assert fake_api == [("olá", [])]


def test_history_excludes_current_question_and_extras(fake_api) -> None:
    session_id = sessions.start_session("p1")
    sessions.answer_pending(session_id)
    sessions.add_question(session_id, "p2")
    sessions.answer_pending(session_id)

    assert fake_api[1] == (
        "p2",
        [
            {"role": "user", "content": "p1"},
            {"role": "assistant", "content": "resposta a p1"},
        ],
    )


def test_history_limited_to_last_ten_messages(fake_api) -> None:
    session_id = sessions.start_session("q0")
    sessions.answer_pending(session_id)
    for number in range(1, 8):
        sessions.add_question(session_id, f"q{number}")
        sessions.answer_pending(session_id)

    history = fake_api[-1][1]
    assert len(history) == 10
    assert history[-1] == {"role": "assistant", "content": "resposta a q6"}


def test_history_skips_answers_without_text(fake_api, fresh_store) -> None:
    session_id = sessions.start_session("p1")
    fresh_store[session_id].append({"role": "assistant", "data": {"answer": None, "error": "x"}})
    sessions.add_question(session_id, "p2")
    sessions.answer_pending(session_id)

    assert fake_api[-1][1] == [{"role": "user", "content": "p1"}]
