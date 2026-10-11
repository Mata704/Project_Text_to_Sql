import streamlit as st

from constants import APP_TITLE, LOGO_SQUARE, PAGE_CHAT, PAGE_CHAT_URL_PATH, PAGE_HOME
from views.constants import CHAT_TITLE, HOME_NAV_TITLE

st.set_page_config(page_title=APP_TITLE, page_icon=LOGO_SQUARE, layout="centered")

pages = [
    st.Page(PAGE_HOME, title=HOME_NAV_TITLE, default=True),
    st.Page(PAGE_CHAT, title=CHAT_TITLE, url_path=PAGE_CHAT_URL_PATH),
]
st.navigation(pages, position="hidden").run()
