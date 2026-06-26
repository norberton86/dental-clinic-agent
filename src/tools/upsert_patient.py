from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import ToolEnvelope, UpsertPatientArgs
from ..services.supabase_client import SupabaseClient, SupabaseError


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run(first_name: str, last_name: str, email: str | None = None) -> str:
        payload = {
            "p_first_name": first_name,
            "p_last_name": last_name,
            "p_phone": phone,
            "p_email": email,
        }
        try:
            data = await client.rpc("upsert_patient", payload)
            return ToolEnvelope.ok(data=data).to_tool_string()
        except SupabaseError as exc:
            return ToolEnvelope.fail(str(exc)).to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="upsert_patient",
        description=(
            "Register a new patient or update an existing one's details (name/email). The phone is "
            "supplied automatically. Returns { patient_id, is_new }."
        ),
        args_schema=UpsertPatientArgs,
    )
