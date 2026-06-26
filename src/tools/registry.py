"""Builds the per-call tool list, binding shared clients + session context.

The caller phone and call_control_id are injected here (closures) — they are
NEVER LLM-supplied arguments.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.tools import BaseTool

from ..graph.confirmation_gate import ConfirmationGate
from ..services.email_service import EmailService
from ..services.supabase_client import SupabaseClient
from ..services.telnyx_client import TelnyxClient
from . import (
    book_appointment_safe,
    cancel_appointment,
    get_appointment_by_phone,
    get_available_slots,
    get_patient_by_phone,
    hangup_call,
    reschedule_appointment_safe,
    send_appointment_email,
    transfer_call,
    upsert_patient,
)


class CallControl:
    """Mutable per-call signal. `hangup_call` sets end_requested and `transfer_call`
    sets transfer_requested; the processor then performs the Telnyx hangup/transfer
    ONLY after the matching spoken line finishes playing (so the goodbye / hand-off
    announcement isn't cut off, which is what happened before)."""

    def __init__(self) -> None:
        self.end_requested = False
        self.transfer_requested = False
        self.transfer_to: str = ""


@dataclass(frozen=True)
class CallSession:
    call_control_id: str
    caller_phone: str  # normalized E.164
    supabase: SupabaseClient
    telnyx: TelnyxClient
    email: EmailService     # SMTP sender for confirmation/reminder emails
    transfer_to: str
    gate: ConfirmationGate  # per-call confirm/validate gate for mutating tools
    control: CallControl    # deferred-hangup signal


def build_tools(session: CallSession) -> list[BaseTool]:
    sb, phone, gate = session.supabase, session.caller_phone, session.gate
    return [
        get_patient_by_phone.make_tool(sb, phone),
        upsert_patient.make_tool(sb, phone),
        get_appointment_by_phone.make_tool(sb, phone),
        get_available_slots.make_tool(sb, phone),
        book_appointment_safe.make_tool(sb, phone, gate),
        reschedule_appointment_safe.make_tool(sb, phone, gate),
        cancel_appointment.make_tool(sb, phone, gate),
        send_appointment_email.make_tool(session.email, sb, phone),
        transfer_call.make_tool(session.control, session.transfer_to),
        hangup_call.make_tool(session.control),
    ]
