from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs
from ..services.supabase_client import SupabaseClient
from ._common import gate_check, rpc_envelope


def make_tool(client: SupabaseClient, phone: str, gate) -> StructuredTool:
    async def _run() -> str:
        blocked = gate_check(gate, "cancel", {})  # no fields to validate; "hold" or proceed
        if blocked is not None:
            return blocked
        return await rpc_envelope(client, "cancel_appointment", {"p_phone": phone})

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
