"""Graph routing with a scripted (mocked) LLM — deterministic, no real model."""
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.graph.agent import build_graph
from src.tools import get_patient_by_phone


class FakeSupabase:
    def __init__(self):
        self.calls = []

    async def rpc(self, fn, payload):
        self.calls.append((fn, payload))
        return [{"patient_id": 7, "first_name": "Daily"}]


class ScriptedLLM:
    """Minimal stand-in for a chat model the graph drives.

    Turn 1: emit a tool call to get_patient_by_phone.
    Turn 2: emit the final spoken greeting (no tool calls -> END).
    """

    def __init__(self):
        self._turn = 0

    def bind_tools(self, tools):
        return self

    async def ainvoke(self, messages):
        self._turn += 1
        if self._turn == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": "get_patient_by_phone", "args": {}, "id": "call_1"}],
            )
        return AIMessage(content="¡Buenos días, Daily! ¿En qué puedo ayudarle?")


@pytest.mark.asyncio
async def test_agent_identifies_caller_then_responds():
    sb = FakeSupabase()
    tools = [get_patient_by_phone.make_tool(sb, "+34600000000")]
    graph = build_graph(ScriptedLLM(), tools, system_prompt="(test prompt)")

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="hola")]},
        {"configurable": {"thread_id": "test-call"}},
    )

    # the patient lookup tool ran
    assert sb.calls == [("get_patient_by_phone", {"p_phone": "+34600000000"})]
    # the final message is the spoken greeting
    final = result["messages"][-1]
    assert "Daily" in final.content
