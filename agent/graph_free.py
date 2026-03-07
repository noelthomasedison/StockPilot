from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from groq import BadRequestError
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_groq import ChatGroq

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from config import GROQ_API_KEY, GROQ_MODEL, MAX_HISTORY_MESSAGES
from agent.prompts import SYSTEM_PROMPT_FREE
from agent.state import AgentState
from agent.tools import (
    get_stock_price,
    get_stock_summary,
    compare_stocks,
    get_stock_news,
)

TOOLS = [
    get_stock_price,
    get_stock_summary,
    compare_stocks,
    get_stock_news,
]

TOOL_BY_NAME = {t.name: t for t in TOOLS}

FAILED_TOOL_RE = re.compile(
    r"<function=(?P<name>\w+)(?P<args>\{.*\})</function>",
    re.DOTALL,
)

TOOL_FORMAT_GUARD = (
    "IMPORTANT: When calling tools, do NOT wrap tool calls in <function>...</function> tags. "
    "Use only the provider's native tool-calling format."
)

FINAL_RESPONSE_GUARD = (
    "Use the tool results already provided and answer the user directly. "
    "Do not call any more tools."
)

MAX_TOOL_CALLS = 2


def _extract_failed_tool_call(err: BadRequestError) -> Optional[Tuple[str, Dict[str, Any]]]:
    body = getattr(err, "body", None) or {}
    error_obj = body.get("error", {}) if isinstance(body, dict) else {}
    failed = error_obj.get("failed_generation")

    if not failed or not isinstance(failed, str):
        return None

    m = FAILED_TOOL_RE.search(failed)
    if not m:
        return None

    name = m.group("name")
    args_str = m.group("args")

    try:
        args = json.loads(args_str)
    except Exception:
        return None

    return name, args


def build_graph():
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY. Put it in your .env file.")

    # Tool-enabled model for planning / tool selection
    llm_with_tools = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.2,
    ).bind_tools(TOOLS)

    # Plain model for final text synthesis only
    llm_plain = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.2,
    )

    raw_tool_node = ToolNode(TOOLS)

    def assistant(state: AgentState) -> AgentState:
        messages = state["messages"][-MAX_HISTORY_MESSAGES:]
        tool_calls = state.get("tool_calls", 0)

        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT_FREE)] + messages

        try:
            resp = llm_with_tools.invoke(messages)
            return {
                "messages": messages + [resp],
                "tool_calls": tool_calls,
            }

        except BadRequestError:
            # Retry once with explicit formatting guard
            try:
                retry_messages = messages + [SystemMessage(content=TOOL_FORMAT_GUARD)]
                resp_retry = llm_with_tools.invoke(retry_messages)
                return {
                    "messages": retry_messages + [resp_retry],
                    "tool_calls": tool_calls,
                }
            except BadRequestError as e2:
                extracted = _extract_failed_tool_call(e2)
                if not extracted:
                    raise

                tool_name, tool_args = extracted
                tool = TOOL_BY_NAME.get(tool_name)
                if tool is None:
                    raise RuntimeError(f"Model attempted unknown tool: {tool_name}")

                tool_result = tool.invoke(tool_args)

                recovered_messages = messages + [
                    ToolMessage(
                        name=tool_name,
                        content=json.dumps(tool_result, ensure_ascii=False),
                        tool_call_id="recovered_tool_call",
                    )
                ]

                # On recovery path, synthesize a final text answer immediately
                final_messages = recovered_messages + [
                    SystemMessage(content=FINAL_RESPONSE_GUARD)
                ]
                final_resp = llm_plain.invoke(final_messages)

                return {
                    "messages": recovered_messages + [final_resp],
                    "tool_calls": tool_calls + 1,
                }

    def tools(state: AgentState) -> AgentState:
        out = raw_tool_node.invoke(state)
        return {
            "messages": out["messages"],
            "tool_calls": state.get("tool_calls", 0) + 1,
        }

    def route_after_tools(state: AgentState) -> str:
        # allow at most 2 tool rounds in free-tier agent 
        if state.get("tool_calls", 0) >= MAX_TOOL_CALLS:
            return "final_assistant"
        return "assistant"

    def final_assistant(state: AgentState) -> AgentState:
        messages = state["messages"][-MAX_HISTORY_MESSAGES:]
        tool_calls = state.get("tool_calls", 0)

        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT_FREE)] + messages

        final_messages = messages + [SystemMessage(content=FINAL_RESPONSE_GUARD)]
        resp = llm_plain.invoke(final_messages)

        return {
            "messages": messages + [resp],
            "tool_calls": tool_calls,
        }

    g = StateGraph(AgentState)
    g.add_node("assistant", assistant)
    g.add_node("tools", tools)
    g.add_node("final_assistant", final_assistant)

    g.add_edge(START, "assistant")
    g.add_conditional_edges(
        "assistant",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        },
    )
    g.add_conditional_edges(
        "tools",
        route_after_tools,
        {
            "assistant": "assistant",
            "final_assistant": "final_assistant",
        },
    )
    g.add_edge("final_assistant", END)

    return g.compile()