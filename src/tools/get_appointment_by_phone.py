from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs, ToolEnvelope
from ..services.supabase_client import SupabaseClient, SupabaseError


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run() -> str:
        try:
            data = await client.rpc("get_appointment_by_phone", {"p_phone": phone})
            return ToolEnvelope.ok(data=data).to_tool_string()
        except SupabaseError as exc:
            return ToolEnvelope.fail(str(exc)).to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="get_appointment_by_phone",
        description=(
            "Return the caller's current active appointment (includes service_name). An EMPTY "
            "array means they have no active appointment. Call before rescheduling/cancelling or "
            "before booking a new one."
        ),
        args_schema=EmptyArgs,
    )
