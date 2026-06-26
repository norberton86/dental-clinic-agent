from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import RescheduleArgs, ToolEnvelope
from ..services.supabase_client import SupabaseClient, SupabaseError


def make_tool(client: SupabaseClient, phone: str, gate) -> StructuredTool:
    async def _run(new_date: str, new_time: str, new_service_name: str | None = None) -> str:
        verdict, msg = gate.evaluate(
            "reschedule",
            {"new_date": new_date, "new_time": new_time, "new_service_name": new_service_name},
        )
        if verdict == "error":
            return ToolEnvelope.fail(msg).to_tool_string()
        if verdict == "hold":
            return ToolEnvelope.pending(msg).to_tool_string()
        payload = {"p_phone": phone, "p_new_date": new_date, "p_new_time": new_time}
        if new_service_name:
            payload["p_new_service_name"] = new_service_name
        try:
            data = await client.rpc("reschedule_appointment_safe", payload)
            return ToolEnvelope.ok(data=data).to_tool_string()
        except SupabaseError as exc:
            return ToolEnvelope.fail(str(exc)).to_tool_string()

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
