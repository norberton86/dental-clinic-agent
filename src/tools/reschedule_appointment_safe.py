from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import RescheduleArgs
from ..services.supabase_client import SupabaseClient
from ._common import gate_check, rpc_envelope


def make_tool(client: SupabaseClient, phone: str, gate) -> StructuredTool:
    async def _run(new_date: str, new_time: str, new_service_name: str | None = None) -> str:
        blocked = gate_check(
            gate,
            "reschedule",
            {"new_date": new_date, "new_time": new_time, "new_service_name": new_service_name},
        )
        if blocked is not None:
            return blocked
        payload = {"p_phone": phone, "p_new_date": new_date, "p_new_time": new_time}
        if new_service_name:
            payload["p_new_service_name"] = new_service_name
        return await rpc_envelope(client, "reschedule_appointment_safe", payload)

    return StructuredTool.from_function(
        coroutine=_run,
        name="reschedule_appointment_safe",
        description=(
            "Move the caller's active appointment. Inputs: new_date YYYY-MM-DD, new_time HH:MM, and "
            "new_service_name ONLY if changing the service. The system enforces confirmation: it "
            "returns 'pending' until you have read the details back and the caller confirmed; call "
            "again with the same args after they say yes."
        ),
        args_schema=RescheduleArgs,
    )
