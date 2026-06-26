"""Tool: email an appointment confirmation/reminder AFTER a successful
book / reschedule / cancel. The agent offers it, gets+confirms the address,
then calls this. The email address is LLM-supplied (read back to the caller);
everything else is built here so the message wording is controlled.
"""
from __future__ import annotations

import re

import structlog
from langchain_core.tools import StructuredTool

from ..models.schemas import AppointmentEmailArgs, ToolEnvelope
from ..services.email_service import EmailService

log = structlog.get_logger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SUBJECTS = {
    "booking": "Confirmación de su cita — Clínica Dental Smile",
    "reschedule": "Cita reprogramada — Clínica Dental Smile",
    "cancellation": "Cancelación de su cita — Clínica Dental Smile",
}


def _build_body(operation: str, name: str, service: str, date: str, time: str) -> str:
    greeting = f"Hola {name}," if name else "Hola,"
    when = " ".join(p for p in (f"el {date}" if date else "", f"a las {time}" if time else "") if p)
    svc = service or "su cita"
    if operation == "cancellation":
        detail = f"Le confirmamos que su cita de {svc} {when} ha sido CANCELADA."
    elif operation == "reschedule":
        detail = f"Su cita ha sido reprogramada: {svc} {when}."
    else:
        detail = f"Le confirmamos su cita: {svc} {when}."
    return (
        f"{greeting}\n\n{detail}\n\n"
        "Gracias por confiar en la Clínica Dental Smile. Si necesita cualquier "
        "cambio, llámenos y estaremos encantados de ayudarle.\n\n"
        "Un saludo,\nClínica Dental Smile"
    )


def make_tool(
    email_service: EmailService,
    supabase=None,
    phone: str = "",
    patient_name_default: str = "",
) -> StructuredTool:
    async def _run(
        email: str,
        operation: str,
        service: str = "",
        date: str = "",
        time: str = "",
        patient_name: str = "",
    ) -> str:
        if not email_service.configured:
            return ToolEnvelope.fail(
                "El envío de correos no está disponible en este momento."
            ).to_tool_string()

        email = (email or "").strip()
        if not _EMAIL_RE.match(email):
            return ToolEnvelope.fail(
                "La dirección de correo no parece válida. Pida al paciente que la "
                "repita y la deletree, y vuelva a intentarlo."
            ).to_tool_string()

        op = operation if operation in _SUBJECTS else "booking"
        subject = _SUBJECTS[op]
        body = _build_body(op, patient_name or patient_name_default, service, date, time)
        try:
            await email_service.send(email, subject, body)
        except Exception as exc:  # noqa: BLE001 - report failure to the agent, keep call alive
            return ToolEnvelope.fail(
                f"No se pudo enviar el correo ({exc}). Discúlpese con el paciente."
            ).to_tool_string()

        # Persist the address to the patient record (email-only update, never blanks
        # the name). Best-effort: a save failure must NOT fail the already-sent email.
        if supabase is not None and phone:
            try:
                await supabase.rpc("update_patient_email", {"p_phone": phone, "p_email": email})
            except Exception as exc:  # noqa: BLE001
                log.warning("email.persist_failed", phone=phone, error=str(exc))

        return ToolEnvelope.ok(message=f"Correo enviado correctamente a {email}.").to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="send_appointment_email",
        description=(
            "Send an appointment confirmation/reminder email AFTER a successful book, "
            "reschedule, or cancel. Only call this once the caller has agreed to receive "
            "an email AND you have read the address back and they confirmed it. Pass the "
            "operation and the service/date/time you just confirmed."
        ),
        args_schema=AppointmentEmailArgs,
    )
