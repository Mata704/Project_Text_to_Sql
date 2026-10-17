from text_to_sql.interaction_logs import InteractionLogService


def test_interaction_logs_share_session_id_and_preserve_event_order() -> None:
    logs = InteractionLogService(session_id="session-test")

    logs.record(
        level="info",
        component="retrieval",
        event="retrieval_started",
        message="Retrieval começou.",
        details={
            "top_k": 5,
            "results": [{"rank": 1, "source": "schema.md", "score": 0.91}],
        },
    )
    logs.record(
        level="warning",
        component="retrieval",
        event="no_evidence",
        message="Não foram encontradas evidências.",
    )

    assert logs.session_id == "session-test"
    assert [entry.event for entry in logs.entries] == ["retrieval_started", "no_evidence"]
    assert logs.entries[0].details == {
        "top_k": 5,
        "results": [{"rank": 1, "source": "schema.md", "score": 0.91}],
    }
    assert logs.entries[0].model_dump(mode="json")["details"]["results"] == [
        {"rank": 1, "source": "schema.md", "score": 0.91}
    ]
    assert logs.entries[1].level == "warning"
