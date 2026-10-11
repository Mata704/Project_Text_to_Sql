import streamlit as st

import sessions
from constants import (
    LOGO_WIDE,
    PAGE_HOME,
    ROLE_USER,
    SESSION_QUERY_PARAM,
    SESSION_STATE_KEY,
)
from details import open_pending_dialog, render_detail_pills
from views.constants import (
    CHAT_TITLE,
    INPUT_PLACEHOLDER,
    INPUT_PLACEHOLDER_WAITING,
    NEW_CONVERSATION_ICON,
    NEW_CONVERSATION_LABEL,
    SESSION_NOT_FOUND_TEXT,
    SPINNER_TEXT,
)

st.logo(LOGO_WIDE, size="large")


def _go_home() -> None:
    st.session_state.pop(SESSION_STATE_KEY, None)
    st.query_params.clear()
    st.switch_page(PAGE_HOME)


session_id = st.query_params.get(SESSION_QUERY_PARAM) or st.session_state.get(SESSION_STATE_KEY)
messages = sessions.get_messages(session_id) if session_id else None
if messages is not None:
    st.session_state[SESSION_STATE_KEY] = session_id
    st.query_params[SESSION_QUERY_PARAM] = session_id

if messages is None:
    st.warning(SESSION_NOT_FOUND_TEXT)
    if st.button(NEW_CONVERSATION_LABEL):
        _go_home()
    st.stop()

st.title(CHAT_TITLE)
st.caption(f"Session ID: `{session_id}`")
if st.sidebar.button(NEW_CONVERSATION_LABEL, icon=NEW_CONVERSATION_ICON, width="stretch"):
    _go_home()

for index, message in enumerate(messages):
    if message["role"] == ROLE_USER:
        with st.chat_message(ROLE_USER):
            st.write(message["content"])
        continue
    data = message["data"]
    with st.chat_message(message["role"]):
        if data.get("error"):
            st.error(data["error"])
        if data.get("answer"):
            st.write(data["answer"])
        render_detail_pills(index)

open_pending_dialog(messages)

awaiting = sessions.is_pending(messages)
follow_up = st.chat_input(
    INPUT_PLACEHOLDER_WAITING if awaiting else INPUT_PLACEHOLDER,
    disabled=awaiting,
)
if follow_up and follow_up.strip():
    sessions.add_question(session_id, follow_up.strip())
    st.rerun()

if awaiting:
    with st.chat_message("assistant"):
        with st.spinner(SPINNER_TEXT):
            sessions.answer_pending(session_id)
    st.rerun()
