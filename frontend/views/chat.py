import pandas as pd
import streamlit as st

import sessions

session_id = st.query_params.get("session") or st.session_state.get("session_id")
messages = sessions.get_messages(session_id) if session_id else None
if messages is not None:
    st.session_state["session_id"] = session_id
    st.query_params["session"] = session_id

if messages is None:
    st.warning("Sessão não encontrada.")
    if st.button("Nova conversa"):
        st.session_state.pop("session_id", None)
        st.query_params.clear()
        st.switch_page("views/home.py")
    st.stop()

st.title("Conversa")
st.caption(f"Session ID: `{session_id}`")
if st.sidebar.button("Nova conversa", icon=":material/add:", use_container_width=True):
    st.session_state.pop("session_id", None)
    st.query_params.clear()
    st.switch_page("views/home.py")


@st.dialog("Logs", width="large")
def show_logs(data: dict) -> None:
    logs = data.get("logs") or []
    if not logs:
        st.info("Sem logs.")
        return
    for entry in logs:
        st.markdown(
            f"`{entry.get('timestamp', '')}` **{entry.get('level', '').upper()}** "
            f"· {entry.get('component', '')} · {entry.get('event', '')}"
        )
        st.write(entry.get("message", ""))
        if entry.get("details"):
            st.json(entry["details"], expanded=False)


@st.dialog("Custos", width="large")
def show_costs(data: dict) -> None:
    metrics = data.get("usageMetrics")
    if not metrics:
        st.info("Sem métricas de utilização.")
        return
    total = metrics.get("total", {})
    cost = total.get("estimated_cost_usd")
    c1, c2, c3 = st.columns(3)
    c1.metric("Custo estimado", f"${cost:.6f}" if cost is not None else "n/d")
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
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    with st.expander("Dados completos"):
        st.json(metrics)


@st.dialog("Evidências", width="large")
def show_evidence(data: dict) -> None:
    evidence = data.get("evidence") or []
    if not evidence:
        st.info("Sem evidências.")
        return
    for item in evidence:
        with st.expander(
            f"#{item['rank']} · {item['source']} · score {item['score']:.3f}"
        ):
            st.caption(f"chunk: {item['chunk_id']}")
            if item.get("citations"):
                st.write("Citações: " + ", ".join(item["citations"]))
            st.text(item["content"])


def _pick(index: int) -> None:
    key = f"pills-{index}"
    choice = st.session_state.get(key)
    if choice:
        st.session_state["open_dialog"] = (index, choice)
    st.session_state[key] = None


for index, message in enumerate(messages):
    if message["role"] == "user":
        with st.chat_message("user"):
            st.write(message["content"])
        continue
    data = message["data"]
    with st.chat_message("assistant"):
        if data.get("error"):
            st.error(data["error"])
        if data.get("answer"):
            st.write(data["answer"])
        st.pills(
            "Detalhes",
            ["Logs", "Custos", "Evidências"],
            key=f"pills-{index}",
            label_visibility="collapsed",
            on_change=_pick,
            args=(index,),
        )

pending = st.session_state.pop("open_dialog", None)
if pending is not None:
    dialog_index, choice = pending
    dialogs = {"Logs": show_logs, "Custos": show_costs, "Evidências": show_evidence}
    dialogs[choice](messages[dialog_index]["data"])

follow_up = st.chat_input("Escreva a sua pergunta...")
if follow_up and follow_up.strip():
    with st.spinner("A processar a pergunta..."):
        sessions.add_turn(session_id, follow_up.strip())
    st.rerun()
