from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import BookArgs, ToolEnvelope
from ..services.supabase_client import SupabaseClient, SupabaseError


def make_tool(client: SupabaseClient, phone: str, gate) -> StructuredTool:
    async def _run(service_name: str, date: str, time: str) -> str:
        verdict, msg = gate.evaluate("book", {"service_name": service_name, "date": date, "time": time})
        if verdict == "error":
            return ToolEnvelope.fail(msg).to_tool_string()
        if verdict == "hold":
            return ToolEnvelope.pending(msg).to_tool_string()
        payload = {"p_phone": phone, "p_service_name": service_name, "p_date": date, "p_time": time}
        try:
            data = await client.rpc("book_appointment_safe", payload)
            return ToolEnvelope.ok(data=data).to_tool_string()
        except SupabaseError as exc:
            return ToolEnvelope.fail(str(exc)).to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="book_appointment_safe",
        description=(
            "Book an appointment for the caller (patient resolved from phone). Inputs: service_name "
            "(Cleaning|Whitening|Extraction), date YYYY-MM-DD, time HH:MM. The system enforces a "
            "confirmation step: it returns status 'pending' until you have read the details back and "
            "the caller has answered yes to '¿Es correcto?'; call again with the same args after they "
            "confirm. May also return 'Patient already has an active appointment'."
        ),
        args_schema=BookArgs,
    )
