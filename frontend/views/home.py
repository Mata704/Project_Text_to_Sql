import streamlit as st

import sessions
from about import show_about
from about.constants import (
    ABOUT_BUTTON_ICON,
    ABOUT_BUTTON_KEY,
    ABOUT_BUTTON_LABEL,
    ABOUT_BUTTON_STYLE,
)
from constants import LOGO_WIDE, PAGE_CHAT, SESSION_STATE_KEY
from views.constants import (
    HOME_CAPTION,
    HOME_HEADER,
    HOME_LOGO_COLUMNS,
    HOME_STYLE,
    INPUT_PLACEHOLDER,
)

st.markdown(HOME_STYLE, unsafe_allow_html=True)

_, logo_col, _ = st.columns(HOME_LOGO_COLUMNS)
logo_col.image(LOGO_WIDE, width="stretch")

st.header(HOME_HEADER, anchor=False)
st.caption(HOME_CAPTION)

question = st.chat_input(INPUT_PLACEHOLDER)

st.markdown(ABOUT_BUTTON_STYLE, unsafe_allow_html=True)
if st.button(ABOUT_BUTTON_LABEL, icon=ABOUT_BUTTON_ICON, key=ABOUT_BUTTON_KEY):
    show_about()
if question and question.strip():
    st.session_state[SESSION_STATE_KEY] = sessions.start_session(question.strip())
    st.switch_page(PAGE_CHAT)
