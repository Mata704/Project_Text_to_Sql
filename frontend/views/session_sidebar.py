import streamlit as st

import api_client
import sessions
from about import show_about
from about.constants import (
    ABOUT_BUTTON_HELP,
    ABOUT_BUTTON_ICON,
    ABOUT_BUTTON_KEY,
    ABOUT_BUTTON_LABEL,
)
from constants import PAGE_CHAT, PAGE_HOME, SESSION_QUERY_PARAM, SESSION_STATE_KEY
from views.constants import NEW_CONVERSATION_ICON, NEW_CONVERSATION_LABEL


def render_session_sidebar(*, on_chat_page: bool, current_session_id: str | None = None) -> None:
    with st.sidebar:
        if st.button(
            ABOUT_BUTTON_LABEL,
            icon=ABOUT_BUTTON_ICON,
            key=ABOUT_BUTTON_KEY,
            help=ABOUT_BUTTON_HELP,
            width="stretch",
        ):
            show_about()
        if on_chat_page:
            start_new = st.button(
                NEW_CONVERSATION_LABEL,
                icon=NEW_CONVERSATION_ICON,
                width="stretch",
                key="new-session",
            )
            if start_new:
                _start_new_session(on_chat_page)
                return
            st.divider()
        st.subheader("Conversas")
        try:
            available_sessions = sessions.list_sessions()
        except api_client.ApiClientError as error:
            st.error(f"Não foi possível carregar as conversas: {error}")
            return

        if not available_sessions:
            st.caption("Ainda não existem conversas.")
            return

        for session in available_sessions:
            session_id = session["sessionId"]
            title = session["title"].strip() or "Nova conversa"
            if len(title) > 32:
                title = f"{title[:29]}..."
            if session_id == current_session_id:
                st.markdown(
                    f"""
                    <style>
                    .st-key-open-session-{session_id} button {{
                        background-color: rgba(128, 128, 128, 0.14) !important;
                        border-color: rgba(128, 128, 128, 0.24) !important;
                        font-weight: 600 !important;
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
            open_col, delete_col = st.columns([0.8, 0.2], gap="small")
            with open_col:
                open_session = st.button(
                    title,
                    key=f"open-session-{session_id}",
                    type="secondary",
                    width="stretch",
                    help=session["title"],
                )
            with delete_col:
                delete_session = st.button(
                    "Eliminar",
                    key=f"delete-session-{session_id}",
                    icon=":material/delete:",
                    help="Eliminar esta conversa",
                )
            if open_session:
                _open_session(session_id, on_chat_page)
                return
            if delete_session:
                _delete_session(
                    session_id,
                    on_chat_page,
                    session_id == current_session_id,
                )
                return


def _start_new_session(on_chat_page: bool) -> None:
    st.session_state.pop(SESSION_STATE_KEY, None)
    st.query_params.clear()
    if on_chat_page:
        st.switch_page(PAGE_HOME)
    st.rerun()


def _open_session(session_id: str, on_chat_page: bool) -> None:
    _navigate_to_session(session_id, on_chat_page)


def _delete_session(session_id: str, on_chat_page: bool, is_current: bool) -> None:
    try:
        sessions.delete_session(session_id)
    except api_client.ApiClientError as error:
        st.error(f"Não foi possível eliminar a conversa: {error}")
        return

    if is_current:
        st.session_state.pop(SESSION_STATE_KEY, None)
        st.query_params.clear()
        if on_chat_page:
            st.switch_page(PAGE_HOME)
            return
    st.rerun()


def _navigate_to_session(session_id: str, on_chat_page: bool) -> None:
    st.session_state[SESSION_STATE_KEY] = session_id
    st.query_params[SESSION_QUERY_PARAM] = session_id
    if on_chat_page:
        st.rerun()
    st.switch_page(PAGE_CHAT)
