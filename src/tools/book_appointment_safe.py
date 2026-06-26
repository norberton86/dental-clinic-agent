from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import BookArgs
from ..services.supabase_client import SupabaseClient
from ._common import gate_check, rpc_envelope


def make_tool(client: SupabaseClient, phone: str, gate) -> StructuredTool:
    async def _run(service_name: str, date: str, time: str) -> str:
        blocked = gate_check(gate, "book", {"service_name": service_name, "date": date, "time": time})
        if blocked is not None:
            return blocked
        payload = {"p_phone": phone, "p_service_name": service_name, "p_date": date, "p_time": time}
        return await rpc_envelope(client, "book_appointment_safe", payload)

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
