import streamlit as st

import api_client
import sessions
from constants import LOGO_WIDE, PAGE_CHAT, SESSION_QUERY_PARAM, SESSION_STATE_KEY
from views.constants import (
    HOME_CAPTION,
    HOME_HEADER,
    HOME_LOGO_COLUMNS,
    HOME_STYLE,
    INPUT_PLACEHOLDER,
)
from views.session_sidebar import render_session_sidebar

st.markdown(HOME_STYLE, unsafe_allow_html=True)
render_session_sidebar(
    on_chat_page=False,
    current_session_id=(
        st.query_params.get(SESSION_QUERY_PARAM) or st.session_state.get(SESSION_STATE_KEY)
    ),
)

_, logo_col, _ = st.columns(HOME_LOGO_COLUMNS)
logo_col.image(LOGO_WIDE, width="stretch")

st.header(HOME_HEADER, anchor=False)
st.caption(HOME_CAPTION)

question = st.chat_input(INPUT_PLACEHOLDER)

if question and question.strip():
    try:
        st.session_state[SESSION_STATE_KEY] = sessions.start_session(question.strip())
    except api_client.ApiClientError as error:
        st.error(str(error))
    else:
        st.switch_page(PAGE_CHAT)
