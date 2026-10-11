import pandas as pd
import streamlit as st

from constants import OPEN_DIALOG_STATE_KEY
from details.constants import (
    DETAIL_COSTS,
    DETAIL_EVIDENCE,
    DETAIL_LOGS,
    DETAIL_OPTIONS,
    DETAILS_PILLS_LABEL,
    DIALOG_WIDTH,
    NO_EVIDENCE_TEXT,
    NO_LOGS_TEXT,
    NO_METRICS_TEXT,
    PILLS_KEY_PREFIX,
    UNAVAILABLE_COST_TEXT,
)


@st.dialog(DETAIL_LOGS, width=DIALOG_WIDTH)
def show_logs(data: dict) -> None:
    logs = data.get("logs") or []
    if not logs:
        st.info(NO_LOGS_TEXT)
        return
    for entry in logs:
        st.markdown(
            f"`{entry.get('timestamp', '')}` **{entry.get('level', '').upper()}** "
            f"· {entry.get('component', '')} · {entry.get('event', '')}"
        )
        st.write(entry.get("message", ""))
        if entry.get("details"):
            st.json(entry["details"], expanded=False)


@st.dialog(DETAIL_COSTS, width=DIALOG_WIDTH)
def show_costs(data: dict) -> None:
    metrics = data.get("usageMetrics")
    if not metrics:
        st.info(NO_METRICS_TEXT)
        return
    total = metrics.get("total", {})
    cost = total.get("estimated_cost_usd")
    c1, c2, c3 = st.columns(3)
    c1.metric("Custo estimado", f"${cost:.6f}" if cost is not None else UNAVAILABLE_COST_TEXT)
    c2.metric("Tokens", total.get("total_tokens", 0))
    c3.metric("Latência", f"{total.get('latency_seconds', 0):.2f} s")
    rows = [
        {
            "Componente": name,
            "Chamadas": comp.get("calls"),
            "Falhadas": comp.get("failed_calls"),
            "Tokens in": comp.get("input_tokens"),
            "Tokens out": comp.get("output_tokens"),
            "Custo (USD)": comp.get("estimated_cost_usd"),
            "Latência (s)": round(comp.get("latency_seconds", 0), 2),
        }
        for name, comp in metrics.get("components", {}).items()
    ]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Dados completos"):
        st.json(metrics)


@st.dialog(DETAIL_EVIDENCE, width=DIALOG_WIDTH)
def show_evidence(data: dict) -> None:
    evidence = data.get("evidence") or []
    if not evidence:
        st.info(NO_EVIDENCE_TEXT)
        return
    for item in evidence:
        with st.expander(f"#{item['rank']} · {item['source']} · score {item['score']:.3f}"):
            st.caption(f"chunk: {item['chunk_id']}")
            if item.get("citations"):
                st.write("Citações: " + ", ".join(item["citations"]))
            st.text(item["content"])


DIALOGS = {
    DETAIL_LOGS: show_logs,
    DETAIL_COSTS: show_costs,
    DETAIL_EVIDENCE: show_evidence,
}


def _pick(index: int) -> None:
    key = f"{PILLS_KEY_PREFIX}{index}"
    choice = st.session_state.get(key)
    if choice:
        st.session_state[OPEN_DIALOG_STATE_KEY] = (index, choice)
    st.session_state[key] = None


def render_detail_pills(index: int) -> None:
    st.pills(
        DETAILS_PILLS_LABEL,
        DETAIL_OPTIONS,
        key=f"{PILLS_KEY_PREFIX}{index}",
        label_visibility="collapsed",
        on_change=_pick,
        args=(index,),
    )


def open_pending_dialog(messages: list[dict]) -> None:
    pending = st.session_state.pop(OPEN_DIALOG_STATE_KEY, None)
    if pending is not None:
        index, choice = pending
        DIALOGS[choice](messages[index]["data"])
