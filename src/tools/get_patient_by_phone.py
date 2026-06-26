from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs, ToolEnvelope
from ..services.supabase_client import SupabaseClient, SupabaseError


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run() -> str:
        try:
            data = await client.rpc("get_patient_by_phone", {"p_phone": phone})
            return ToolEnvelope.ok(data=data).to_tool_string()
        except SupabaseError as exc:
            return ToolEnvelope.fail(str(exc)).to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="get_patient_by_phone",
        description=(
            "Identify the caller by their phone number (already known). Returns an array of "
            "patient records; an EMPTY array means the caller is not registered yet."
        ),
        args_schema=EmptyArgs,
    )
