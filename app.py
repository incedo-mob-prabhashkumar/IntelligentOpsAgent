from __future__ import annotations

import streamlit as st

from src.config import get_settings
from src.service import ITSupportAgent


settings = get_settings()

st.set_page_config(page_title=settings.app_name, page_icon="🛠", layout="wide")
st.title(settings.app_name)
st.caption("LangGraph workflow, local LLM routing, PostgreSQL-backed tools, and multi-turn state handling")


def _render_tool_result_table(trace: dict | None) -> None:
    if not trace:
        return
    tool_result = trace.get("tool_result", {})
    tool_name = tool_result.get("tool")
    data = tool_result.get("data")

    if not tool_name or data is None:
        return

    st.caption(f"Tabular business response: {tool_name}")

    if tool_name == "ticket_lookup":
        rows = data.get("tickets", []) if isinstance(data, dict) else []
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.dataframe([], width="stretch", hide_index=True)
        return

    if tool_name == "knowledge_search":
        rows = data.get("matches", []) if isinstance(data, dict) else []
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.dataframe([], width="stretch", hide_index=True)
        return

    if tool_name == "employee_lookup":
        rows = data.get("employees", []) if isinstance(data, dict) else []
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.dataframe([], width="stretch", hide_index=True)
        return

    if tool_name == "system_status":
        rows = data.get("statuses", []) if isinstance(data, dict) else []
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.dataframe([], width="stretch", hide_index=True)
        return

    if tool_name == "ticket_creation":
        row = data.get("ticket", {}) if isinstance(data, dict) else {}
        if row:
            st.dataframe([row], width="stretch", hide_index=True)
        return

    if tool_name == "ticket_update":
        row = data.get("ticket", {}) if isinstance(data, dict) else {}
        if row:
            st.dataframe([row], width="stretch", hide_index=True)
        return

    if tool_name == "duplicate_check":
        if isinstance(data, dict) and data:
            st.dataframe([data], width="stretch", hide_index=True)
        return

    if isinstance(data, list):
        st.dataframe(data, width="stretch", hide_index=True)
    elif isinstance(data, dict):
        st.dataframe([data], width="stretch", hide_index=True)

if "agent" not in st.session_state:
    st.session_state.agent = ITSupportAgent()
if "agent_context" not in st.session_state:
    st.session_state.agent_context = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

database_status = st.session_state.agent.database_status
if not database_status.ready:
    st.warning(
        "Database startup validation did not complete. Ticket and knowledge-base actions may be unavailable. "
        f"Details: {database_status.message}"
    )
    if "does not exist" in database_status.message.lower():
        st.info("Database setup hint: create the database first, then restart the app.")
        st.code("createdb -h localhost -U postgres it_support", language="bash")

col_left, col_right = st.columns([6, 2])
with col_left:
    st.info(
        "Supported tasks: knowledge-base answers, system status checks, ticket status lookup, and support ticket creation. "
        "For ticket actions, include or follow up with your employee ID such as EMP1024."
    )
with col_right:
    if st.button("Clear Conversation", width="stretch"):
        st.session_state.agent_context = {}
        st.session_state.chat_history = []
        st.rerun()

for turn in st.session_state.chat_history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        trace = turn.get("trace")
        if turn["role"] == "assistant":
            _render_tool_result_table(trace)
        if settings.show_trace and trace and turn["role"] == "assistant":
            with st.expander("Tool / Routing Details"):
                st.json(trace)

user_message = st.chat_input("Ask for IT help. Example: My VPN is not working. Please raise a ticket.")

if user_message:
    st.session_state.chat_history.append({"role": "user", "content": user_message})

    with st.chat_message("user"):
        st.markdown(user_message)

    response, next_context, trace = st.session_state.agent.handle_message(
        user_message=user_message,
        context=st.session_state.agent_context,
    )
    st.session_state.agent_context = next_context

    with st.chat_message("assistant"):
        st.markdown(response)
        _render_tool_result_table(trace)
        if settings.show_trace:
            with st.expander("Tool / Routing Details"):
                st.json(trace)

    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": response,
            "trace": trace,
        }
    )
