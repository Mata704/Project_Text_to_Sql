from pathlib import Path

import streamlit as st

import sessions

ASSETS = Path(__file__).parent.parent / "assets"

st.image(str(ASSETS / "logo_wide.png"), width=520)
st.title("Pergunte sobre comboios")
st.caption("Escreva a sua pergunta para iniciar uma nova sessão.")

question = st.chat_input("Escreva a sua pergunta...")
if question and question.strip():
    with st.spinner("A processar a pergunta..."):
        session_id = sessions.start_session(question.strip())
    st.session_state["session_id"] = session_id
    st.switch_page("views/chat.py")
