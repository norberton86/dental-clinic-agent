"""Shared helpers for tool implementations.

Every tool turns an RPC call (and the confirmation gate, for mutating tools) into
the standard ToolEnvelope JSON string. These helpers remove that repeated
boilerplate so each tool reads as just "what it does".
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..models.schemas import ToolEnvelope
from ..services.supabase_client import SupabaseClient, SupabaseError


async def rpc_envelope(
    client: SupabaseClient,
    fn: str,
    payload: dict,
    transform: Callable[[Any], Any] | None = None,
) -> str:
    """Call a Supabase RPC and wrap success/error in the standard envelope string.
    `transform` optionally post-processes the returned data before it is wrapped
    (e.g. to enrich rows with a computed field)."""
    try:
        data = await client.rpc(fn, payload)
        if transform is not None:
            data = transform(data)
        return ToolEnvelope.ok(data=data).to_tool_string()
    except SupabaseError as exc:
        return ToolEnvelope.fail(str(exc)).to_tool_string()


def gate_check(gate, action: str, args: dict) -> str | None:
    """Run the confirmation gate. Return an envelope string if it blocks the action
    ("error" → fail, "hold" → pending), or None when the action may proceed."""
    verdict, msg = gate.evaluate(action, args)
    if verdict == "error":
        return ToolEnvelope.fail(msg).to_tool_string()
    if verdict == "hold":
        return ToolEnvelope.pending(msg).to_tool_string()
    return None
