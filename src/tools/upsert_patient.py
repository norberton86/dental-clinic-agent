from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import UpsertPatientArgs
from ..services.supabase_client import SupabaseClient
from ._common import rpc_envelope


def make_tool(client: SupabaseClient, phone: str) -> StructuredTool:
    async def _run(first_name: str, last_name: str, email: str | None = None) -> str:
        payload = {
            "p_first_name": first_name,
            "p_last_name": last_name,
            "p_phone": phone,
            "p_email": email,
        }
        return await rpc_envelope(client, "upsert_patient", payload)

    return StructuredTool.from_function(
        coroutine=_run,
        name="upsert_patient",
        description=(
            "Register a new patient or update an existing one's details (name/email). The phone is "
            "supplied automatically. Returns { patient_id, is_new }."
        ),
        args_schema=UpsertPatientArgs,
    )
