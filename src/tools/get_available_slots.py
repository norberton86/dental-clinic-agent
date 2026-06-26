from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import AvailableSlotsArgs
from ..services.supabase_client import SupabaseClient
from ._common import rpc_envelope


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run(service_name: str, date: str) -> str:
        return await rpc_envelope(
            client, "get_available_slots", {"p_service_name": service_name, "p_date": date}
        )

    return StructuredTool.from_function(
        coroutine=_run,
        name="get_available_slots",
        description=(
            "Return up to 5 available time slots for a service on a date. service_name must be "
            "exactly Cleaning, Whitening or Extraction; date is YYYY-MM-DD. EMPTY array = no "
            "availability that day."
        ),
        args_schema=AvailableSlotsArgs,
    )
