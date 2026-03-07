from __future__ import annotations

from langchain_core.messages import SystemMessage
from langchain_groq import ChatGroq

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from config import GROQ_API_KEY, GROQ_MODEL
from agent.prompts import SYSTEM_PROMPT_PRO as SYSTEM_PROMPT
from agent.state import AgentState
from agent.tools import (
    get_stock_price,
    get_stock_history,
    compute_stock_metrics,
    compare_stocks,
    get_stock_news,
)

TOOLS = [
    get_stock_price,
    get_stock_history,
    compute_stock_metrics,
    compare_stocks,
    get_stock_news,
]


def build_graph():
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY. Put it in your .env file.")

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.2,
    ).bind_tools(TOOLS)

    tool_node = ToolNode(TOOLS)

    def assistant(state: AgentState) -> AgentState:
        messages = state["messages"]
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        resp = llm.invoke(messages)
        return {"messages": messages + [resp]}

    g = StateGraph(AgentState)
    g.add_node("assistant", assistant)
    g.add_node("tools", tool_node)

    g.add_edge(START, "assistant")
    g.add_conditional_edges("assistant", tools_condition)
    g.add_edge("tools", "assistant")
    g.add_edge("assistant", END)

    return g.compile()