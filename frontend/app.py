import streamlit as st

from constants import APP_TITLE, LOGO_SQUARE, PAGE_CHAT, PAGE_CHAT_URL_PATH, PAGE_HOME
from views.constants import CHAT_TITLE, HOME_NAV_TITLE

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=LOGO_SQUARE,
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stExpandSidebarButton"] {
        display: none !important;
    }
    [data-testid="stSidebar"] {
        position: fixed !important;
        top: 0 !important;
        bottom: 0 !important;
        left: 0 !important;
        height: 100vh !important;
        max-height: 100vh !important;
    }
    [data-testid="stSidebar"] > div {
        height: 100% !important;
        overflow-y: auto;
    }
    [data-testid="stSidebar"][aria-expanded="false"] {
        min-width: 21rem !important;
        width: 21rem !important;
        transform: translateX(calc(-100% + 1.5rem)) !important;
        visibility: visible !important;
        transition: transform 220ms ease-in-out, box-shadow 220ms ease-in-out !important;
        z-index: 1000000 !important;
        border-right: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 0 16px 16px 0;
        box-shadow: 2px 0 10px rgba(0, 0, 0, 0.12);
    }
    [data-testid="stSidebar"][aria-expanded="false"]::after {
        content: "\\203A";
        position: absolute;
        top: 50%;
        right: 0;
        width: 1.5rem;
        height: 4rem;
        margin-top: -2rem;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.6rem;
        font-weight: 700;
        color: rgba(128, 128, 128, 0.8);
        background: linear-gradient(90deg, rgba(128, 128, 128, 0.04), rgba(128, 128, 128, 0.14));
        border-radius: 0 12px 12px 0;
        transition: opacity 150ms ease-in-out;
    }
    [data-testid="stSidebar"][aria-expanded="false"]:hover,
    [data-testid="stSidebar"][aria-expanded="false"]:focus-within {
        transform: translateX(0) !important;
        box-shadow: 6px 0 24px rgba(0, 0, 0, 0.22);
    }
    [data-testid="stSidebar"][aria-expanded="false"]:hover::after,
    [data-testid="stSidebar"][aria-expanded="false"]:focus-within::after {
        opacity: 0;
    }
    [data-testid="stSidebarHeader"] {
        display: none !important;
    }
    [data-testid="stSidebar"] > div > div {
        padding-top: 1.25rem;
    }
    [data-testid="stSidebar"][aria-expanded="false"] > div {
        visibility: hidden;
    }
    [data-testid="stSidebar"][aria-expanded="false"]:hover > div,
    [data-testid="stSidebar"][aria-expanded="false"]:focus-within > div {
        visibility: visible;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

pages = [
    st.Page(PAGE_HOME, title=HOME_NAV_TITLE, default=True),
    st.Page(PAGE_CHAT, title=CHAT_TITLE, url_path=PAGE_CHAT_URL_PATH),
]
st.navigation(pages, position="hidden").run()
