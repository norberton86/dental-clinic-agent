from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs, ToolEnvelope
from ..services.supabase_client import SupabaseClient, SupabaseError


def make_tool(client: SupabaseClient, phone: str, gate) -> StructuredTool:
    async def _run() -> str:
        verdict, msg = gate.evaluate("cancel", {})
        if verdict == "hold":
            return ToolEnvelope.pending(msg).to_tool_string()
        # (no fields to validate for cancel; verdict is "hold" or "execute")
        try:
            data = await client.rpc("cancel_appointment", {"p_phone": phone})
            return ToolEnvelope.ok(data=data).to_tool_string()
        except SupabaseError as exc:
            return ToolEnvelope.fail(str(exc)).to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="cancel_appointment",
        description=(
            "Cancel the caller's active appointment (patient resolved from phone). The system "
            "enforces confirmation: it returns 'pending' until you have read back which appointment "
            "and the caller confirmed; call again after they say yes."
        ),
        args_schema=EmptyArgs,
    )
