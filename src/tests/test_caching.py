"""Prompt-caching marker behaviour.

Anthropic needs an explicit cache_control marker; OpenAI/Telnyx (Kimi) cache
automatically on a stable prefix, so they must get a PLAIN system message (no
marker — the marker is Anthropic-only and not portable to OpenAI-compatible APIs).
"""
from langchain_core.messages import SystemMessage

from src.graph.nodes import build_system_message


def test_plain_message_for_automatic_providers():
    msg = build_system_message("hola", cache=False)
    assert isinstance(msg, SystemMessage)
    assert msg.content == "hola"  # plain str -> OpenAI/Telnyx automatic caching


def test_anthropic_cache_control_marker():
    msg = build_system_message("hola", cache=True)
    assert isinstance(msg.content, list)
    block = msg.content[0]
    assert block["type"] == "text"
    assert block["text"] == "hola"
    assert block["cache_control"] == {"type": "ephemeral"}
