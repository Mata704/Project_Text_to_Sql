from pathlib import Path

import streamlit as st

import sessions

ASSETS = Path(__file__).parent.parent / "assets"

st.markdown(
    "<style>.block-container{padding-top:3rem;max-width:960px}"
    "[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
    "[data-testid='stLogo']{display:none}"
    "[data-testid='stHeading'],[data-testid='stCaptionContainer']"
    "{text-align:center;justify-content:center}</style>",
    unsafe_allow_html=True,
)

_, logo_col, _ = st.columns([1, 5, 1])
logo_col.image(str(ASSETS / "logo_wide.png"), use_container_width=True)

st.header("Pergunte sobre comboios", anchor=False)
st.caption("Escreva a sua pergunta para iniciar uma nova sessão.")

question = st.chat_input("Escreva a sua pergunta...")
if question and question.strip():
    st.session_state["session_id"] = sessions.start_session(question.strip())
    st.switch_page("views/chat.py")
