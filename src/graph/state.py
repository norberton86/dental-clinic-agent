from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Conversation state. `messages` is the running transcript (MemorySaver-backed)."""

    messages: Annotated[list, add_messages]
