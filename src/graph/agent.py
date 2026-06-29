"""LangGraph ReAct agent: agent ⇄ tools loop, MemorySaver checkpointer."""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from ..config.settings import Settings
from .nodes import make_agent_node
from .state import AgentState


def make_llm(settings: Settings) -> BaseChatModel:
    """Construct the chat model from config.

    Default is `telnyx` → Kimi-K2.6 over Telnyx's OpenAI-compatible inference
    endpoint (cheap, strong tool discipline — validated). `openai`/`anthropic`
    remain available. Streaming on so the processor can pipe tokens to TTS.
    """
    if settings.llm_provider == "telnyx":
        from langchain_openai import ChatOpenAI

        # OpenAI-compatible; the client appends /chat/completions to base_url.
        return ChatOpenAI(
            model=settings.telnyx_inference_model,
            api_key=settings.telnyx_api_key,
            base_url="https://api.telnyx.com/v2/ai",
            temperature=0.2,
            streaming=True,
        )

    if settings.llm_provider == "gemini":
        from langchain_openai import ChatOpenAI

        # Gemini via its OpenAI-compatible endpoint (reuses ChatOpenAI). max_retries
        # covers the free tier's transient 503 "high demand" spikes.
        return ChatOpenAI(
            model=settings.gemini_model,
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_base_url,
            temperature=0.3,
            streaming=True,
            stream_usage=True,  # emit token usage during streaming (else metrics read 0)
            max_retries=4,
        )

    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key,
            temperature=0.3,
            max_tokens=1024,
            streaming=True,
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.3,
        streaming=True,
    )


def build_graph(
    llm: BaseChatModel, tools: list[BaseTool], system_prompt: str, cache_system: bool = False
):
    """Compile the per-call graph. Memory is keyed by thread_id at invocation time.

    cache_system=True applies Anthropic `cache_control` markers to the system block
    (explicit caching). Leave False for OpenAI/Telnyx — they cache automatically.
    """
    llm_with_tools = llm.bind_tools(tools)
    agent_node = make_agent_node(llm_with_tools, system_prompt, cache_system=cache_system)

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=MemorySaver())
