from __future__ import annotations

from typing import TypedDict, List
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    messages: List[BaseMessage]
    tool_calls: int

# PHASE 2:
# - Add memory fields like last_ticker, last_comparison, user_preferences, etc.
# - Add validation flags / tool trace if you want rich UI updatess