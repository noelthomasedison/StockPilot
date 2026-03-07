from __future__ import annotations

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from config import (
    APP_TITLE,
    APP_SUBTITLE,
    STOCKPILOT_MODE as ENV_MODE,
    MAX_HISTORY_MESSAGES as ENV_MAX_HISTORY,
    FAST_PATH as ENV_ENABLE_FAST_PATH
)

from agent.preparser import detect_intent
from agent.formatters import format_price, format_summary, format_compare, format_news
from agent.tools import get_stock_price, get_stock_summary, compare_stocks, get_stock_news


st.set_page_config(page_title="StockPilot", layout="centered")

st.title(APP_TITLE)
st.caption(APP_SUBTITLE)

# ---------------- Session State ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_plan" not in st.session_state:
    st.session_state.last_plan = None
if "pending_user_text" not in st.session_state:
    st.session_state.pending_user_text = None
if "show_tool_traces" not in st.session_state:
    st.session_state.show_tool_traces = False

# Runtime settings
if "mode" not in st.session_state:
    st.session_state.mode = ENV_MODE
if "max_history" not in st.session_state:
    st.session_state.max_history = int(ENV_MAX_HISTORY)
if "enable_fast_path" not in st.session_state:
    st.session_state.enable_fast_path = bool(ENV_ENABLE_FAST_PATH)

# ---------------- Sidebar: Settings + Plan ----------------
tab_settings, tab_plan = st.sidebar.tabs(["⚙️ Settings", "🧭 Plan"])

with tab_settings:
    st.markdown("### StockPilot Settings")

    st.session_state.mode = st.radio(
        "Mode",
        options=["free", "pro"],
        index=0 if st.session_state.mode == "free" else 1,
        horizontal=True,
    )

    st.session_state.max_history = st.slider(
        "MAX_HISTORY_MESSAGES",
        min_value=2,
        max_value=30,
        value=int(st.session_state.max_history),
        step=1,
    )

    st.session_state.enable_fast_path = st.checkbox(
        "Enable Fast Path (single-tool routing)",
        value=bool(st.session_state.enable_fast_path),
        help="""For simple queries, StockPilot detects the intent and directly calls one tool 
        without using the LangGraph agent.

        Example:
        "AAPL price" → get_stock_price  
        "AAPL this month performance" → get_stock_summary

        For More complex questions use the LangGraph agent(Disable Fast Path).
        """,
        )

    st.session_state.show_tool_traces = st.checkbox(
        "Show tool traces (debug)",
        value=bool(st.session_state.show_tool_traces),
        help="Show ToolMessage outputs in chat for debugging.",
    )

with tab_plan:
    st.markdown("### Plan")
    if st.session_state.last_plan is None:
        st.info("No plan yet. Ask a question.")
    else:
        st.json(st.session_state.last_plan)


# ---------------- Build / Switch Graph when mode changes ----------------
def build_selected_graph():
    if st.session_state.mode == "pro":
        from agent.graph_pro import build_graph
    else:
        from agent.graph_free import build_graph
    return build_graph()


if (
    "graph" not in st.session_state
    or st.session_state.get("graph_mode") != st.session_state.mode
):
    st.session_state.graph = build_selected_graph()
    st.session_state.graph_mode = st.session_state.mode


# ---------------- Process pending input (before rendering chat input) ----------------
def handle_user_text(user_text: str) -> None:
    """Appends messages + runs fast path or agent. Updates last_plan."""
    st.session_state.messages.append(HumanMessage(content=user_text))

    detected_plan = detect_intent(user_text)

    fast_path_allowed = (
        st.session_state.enable_fast_path
        and detected_plan is not None
    )

    # ---------------- FAST PATH ----------------
    if fast_path_allowed:
        tools_called: list[str] = []

        try:
            if detected_plan["intent"] == "price":
                res = get_stock_price.invoke({"ticker": detected_plan["ticker"]})
                tools_called.append("get_stock_price")
                st.session_state.messages.append(
                    AIMessage(content="⚡ Fast path (pre-parser)\n\n" + format_price(res))
                )

            elif detected_plan["intent"] == "summary":
                res = get_stock_summary.invoke(
                    {"ticker": detected_plan["ticker"], "period": detected_plan["period"]}
                )
                tools_called.append("get_stock_summary")
                st.session_state.messages.append(
                    AIMessage(content="⚡ Fast path (pre-parser)\n\n" + format_summary(res))
                )

            elif detected_plan["intent"] == "compare":
                res = compare_stocks.invoke(
                    {
                        "ticker_a": detected_plan["a"],
                        "ticker_b": detected_plan["b"],
                        "period": detected_plan["period"],
                    }
                )
                tools_called.append("compare_stocks")
                st.session_state.messages.append(
                    AIMessage(content="⚡ Fast path (pre-parser)\n\n" + format_compare(res))
                )

            elif detected_plan["intent"] == "news":
                res = get_stock_news.invoke({"ticker_or_query": detected_plan["query"]})
                tools_called.append("get_stock_news")
                st.session_state.messages.append(
                    AIMessage(content="⚡ Fast path (pre-parser)\n\n" + format_news(res))
                )

            else:
                fast_path_allowed = False

            if fast_path_allowed:
                st.session_state.last_plan = {
                    "query": user_text,
                    "mode": st.session_state.mode,
                    "path": "fast_path",
                    "detected_plan": detected_plan,
                    "tools_called": tools_called,
                }

        except Exception as e:
            st.session_state.messages.append(AIMessage(content=f"Fast path error: {e}"))
            st.session_state.last_plan = {
                "query": user_text,
                "mode": st.session_state.mode,
                "path": "fast_path_error",
                "detected_plan": detected_plan,
                "tools_called": tools_called,
                "error": str(e),
            }
            fast_path_allowed = False

    # ---------------- AGENT PATH ----------------
    if not fast_path_allowed:
        trimmed = [
            m for m in st.session_state.messages[-int(st.session_state.max_history):]
            if not isinstance(m, ToolMessage)
        ]

        result = st.session_state.graph.invoke({"messages": trimmed})
        out_msgs = result["messages"]

        # Remove prepended SystemMessage if present
        if out_msgs and out_msgs[0].__class__.__name__ == "SystemMessage":
            out_core = out_msgs[1:]
        else:
            out_core = out_msgs

        tool_msgs = [m for m in out_core if isinstance(m, ToolMessage)]
        ai_msgs = [
            m for m in out_core
            if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip()
        ]

        new_part = []

        # Prefer a proper assistant reply
        if ai_msgs:
            last_ai = ai_msgs[-1]
            new_part.append(
                AIMessage(content="🧠 Agent path (LangGraph)\n\n" + last_ai.content)
            )

        # If no assistant reply exists, still show a graceful fallback
        elif tool_msgs:
            new_part.append(
                AIMessage(
                    content=(
                        "🧠 Agent path (LangGraph)\n\n"
                        "I retrieved the relevant tool output, but the final synthesis step did not return a full reply."
                    )
                )
            )

        # Absolute fallback
        else:
            new_part.append(
                AIMessage(
                    content="⚠️ Agent executed but produced no visible response. Try a simpler query."
                )
            )

        # Show raw tool traces only in debug mode
        if st.session_state.show_tool_traces:
            new_part = tool_msgs + new_part

        st.session_state.messages.extend(new_part)

        tools_called = [m.name for m in tool_msgs]

        st.session_state.last_plan = {
            "query": user_text,
            "mode": st.session_state.mode,
            "path": "agent_path",
            "detected_plan": detected_plan,
            "tools_called": tools_called,
            "tool_count": len(tools_called),
        }


# If there’s pending input, process it once and rerun so UI shows it above input.
if st.session_state.pending_user_text is not None:
    txt = st.session_state.pending_user_text
    st.session_state.pending_user_text = None
    handle_user_text(txt)
    st.rerun()


# ---------------- Render chat history ----------------
for m in st.session_state.messages:
    if isinstance(m, HumanMessage):
        with st.chat_message("user"):
            st.markdown(m.content)

    elif isinstance(m, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(m.content)

    elif isinstance(m, ToolMessage):
        if st.session_state.show_tool_traces:
            with st.chat_message("assistant"):
                with st.expander(f"🔧 Tool output: {m.name}", expanded=False):
                    st.code(m.content)


# ---------------- Chat input (always at bottom) ----------------
user_text = st.chat_input("Ask me about any stock… (e.g., 'AAPL this month + recent news')")
if user_text:
    st.session_state.pending_user_text = user_text
    st.rerun()