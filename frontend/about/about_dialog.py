import streamlit as st

from about.constants import (
    ABOUT_AUTHOR,
    ABOUT_DIAGRAM_COLUMNS,
    ABOUT_DIAGRAM_HEADER,
    ABOUT_DIALOG_TITLE,
    ABOUT_DIALOG_WIDTH,
    ABOUT_LOGO_COLUMNS,
    ABOUT_PROJECT_TITLE,
    ABOUT_STYLE,
    ABOUT_SUMMARY_CARDS,
    ABOUT_SUMMARY_HEADER,
)
from constants import DIAGRAM_IMAGE, LOGO_WIDE


@st.dialog(ABOUT_DIALOG_TITLE, width=ABOUT_DIALOG_WIDTH)
def show_about() -> None:
    st.markdown(ABOUT_STYLE, unsafe_allow_html=True)
    _, logo_col, _ = st.columns(ABOUT_LOGO_COLUMNS)
    logo_col.image(LOGO_WIDE, width="stretch")
    st.markdown(f"<div class='about-title'>{ABOUT_PROJECT_TITLE}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='about-author'>{ABOUT_AUTHOR}</div>", unsafe_allow_html=True)

    st.subheader(ABOUT_SUMMARY_HEADER, anchor=False)
    for column, (icon, title, text) in zip(
        st.columns(len(ABOUT_SUMMARY_CARDS)), ABOUT_SUMMARY_CARDS, strict=True
    ):
        with column.container(border=True, height="stretch"):
            st.markdown(icon)
            st.markdown(f"<div class='about-card-title'>{title}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='about-card-text'>{text}</div>", unsafe_allow_html=True)

    st.subheader(ABOUT_DIAGRAM_HEADER, anchor=False)
    _, diagram_col, _ = st.columns(ABOUT_DIAGRAM_COLUMNS)
    with diagram_col.container(border=True):
        st.image(DIAGRAM_IMAGE, width="stretch")
