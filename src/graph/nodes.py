from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from .state import AgentState


def build_system_message(system_prompt: str, cache: bool) -> SystemMessage:
    """Build the per-call system message.

    When `cache` is True (Anthropic), tag the content block with `cache_control`
    so Anthropic caches the static prefix (tools + system, ~3k tokens). For
    OpenAI / Telnyx (Kimi) `cache` is False — those providers cache automatically
    on a stable prefix, so NO marker is sent (the marker is Anthropic-only and
    would be meaningless/ignored elsewhere).
    """
    if cache:
        return SystemMessage(
            content=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
        )
    return SystemMessage(content=system_prompt)


def make_agent_node(
    llm_with_tools: BaseChatModel, system_prompt: str, cache_system: bool = False
) -> Callable[[AgentState], Awaitable[dict]]:
    """The 'agent' node: calls the LLM (with tools bound), prepending the per-call
    system prompt (kept identical every turn so prompt caching hits)."""
    system_message = build_system_message(system_prompt, cache_system)

    async def agent_node(state: AgentState) -> dict:
        response = await llm_with_tools.ainvoke([system_message, *state["messages"]])
        return {"messages": [response]}

    return agent_node
