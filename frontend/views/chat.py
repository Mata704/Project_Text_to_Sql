import streamlit as st

import api_client
import sessions
from constants import (
    ROLE_USER,
    SESSION_QUERY_PARAM,
    SESSION_STATE_KEY,
)
from details import open_pending_dialog, render_detail_pills
from views.constants import (
    CHAT_TITLE,
    INPUT_PLACEHOLDER,
    INPUT_PLACEHOLDER_WAITING,
    SESSION_NOT_FOUND_TEXT,
    SPINNER_TEXT,
)
from views.session_sidebar import render_session_sidebar

session_id = st.query_params.get(SESSION_QUERY_PARAM) or st.session_state.get(SESSION_STATE_KEY)
try:
    messages = sessions.get_messages(session_id) if session_id else None
except api_client.ApiClientError as error:
    st.error(str(error))
    st.stop()
if messages is not None:
    st.session_state[SESSION_STATE_KEY] = session_id
    st.query_params[SESSION_QUERY_PARAM] = session_id

if messages is None:
    st.warning(SESSION_NOT_FOUND_TEXT)
    render_session_sidebar(on_chat_page=True)
    st.stop()

render_session_sidebar(on_chat_page=True, current_session_id=session_id)
st.title(CHAT_TITLE)
st.caption(f"Session ID: `{session_id}`")

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
    try:
        sessions.add_question(session_id, follow_up.strip())
    except api_client.ApiClientError as error:
        st.error(str(error))
    else:
        st.rerun()

if awaiting:
    with st.chat_message("assistant"):
        with st.spinner(SPINNER_TEXT):
            try:
                sessions.answer_pending(session_id)
            except api_client.ApiClientError as error:
                st.error(str(error))
            else:
                st.rerun()
