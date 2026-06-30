from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import AvailableSlotsArgs
from ..services.supabase_client import SupabaseClient
from ._common import rpc_envelope


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run(
        service_name: str, date: str, from_time: str | None = None, to_time: str | None = None
    ) -> str:
        return await rpc_envelope(
            client,
            "get_available_slots",
            {
                "p_service_name": service_name,
                "p_date": date,
                "p_from_time": from_time,
                "p_to_time": to_time,
            },
        )

    return StructuredTool.from_function(
        coroutine=_run,
        name="get_available_slots",
        description=(
            "Return up to 5 available time slots for a service on a date. service_name must be "
            "exactly Cleaning, Whitening or Extraction; date is YYYY-MM-DD. Pass from_time/to_time "
            "(HH:MM) to restrict to a window the caller asked for (e.g. 'entre las 9 y las 11' -> "
            "from_time '09:00', to_time '11:00'); omit them when there is no time preference. "
            "EMPTY array = no availability (in that window, if one was given)."
        ),
        args_schema=AvailableSlotsArgs,
    )
