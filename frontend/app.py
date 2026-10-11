from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"

st.set_page_config(
    page_title="Comboios Pedro Mata",
    page_icon=str(ASSETS / "logo_square.png"),
    layout="centered",
)

pages = [
    st.Page("views/home.py", title="Início", default=True),
    st.Page("views/chat.py", title="Conversa", url_path="chat"),
]
st.navigation(pages, position="hidden").run()
