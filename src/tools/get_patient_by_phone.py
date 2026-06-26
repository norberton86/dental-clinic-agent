from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs
from ..services.supabase_client import SupabaseClient
from ._common import rpc_envelope


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run() -> str:
        return await rpc_envelope(client, "get_patient_by_phone", {"p_phone": phone})

    return StructuredTool.from_function(
        coroutine=_run,
        name="get_patient_by_phone",
        description=(
            "Identify the caller by their phone number (already known). Returns an array of "
            "patient records; an EMPTY array means the caller is not registered yet."
        ),
        args_schema=EmptyArgs,
    )
