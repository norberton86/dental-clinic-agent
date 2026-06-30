from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs
from ..services.supabase_client import SupabaseClient
from ..utils.dates import spanish_weekday
from ._common import rpc_envelope


def _add_weekday(rows):
    # Attach the correct Spanish weekday so the agent reads it back instead of
    # computing it (it has mislabelled weekdays, e.g. a Friday as "jueves").
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("appointment_date"):
                wd = spanish_weekday(row["appointment_date"])
                if wd:
                    row["weekday"] = wd
    return rows


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run() -> str:
        return await rpc_envelope(
            client, "get_appointment_by_phone", {"p_phone": phone}, transform=_add_weekday
        )

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
