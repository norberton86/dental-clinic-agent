"""Tool: email an appointment confirmation/reminder AFTER a successful
book / reschedule / cancel. The agent offers it, gets+confirms the address,
then calls this. The email address is LLM-supplied (read back to the caller);
everything else is built here so the message wording is controlled.
"""
from __future__ import annotations

import re
from html import escape

import structlog
from langchain_core.tools import StructuredTool

from ..models.schemas import AppointmentEmailArgs, ToolEnvelope
from ..services.calendar_links import build_calendar_links, select_links_for_email
from ..services.email_service import EmailService

log = structlog.get_logger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SUBJECTS = {
    "booking": "Confirmación de su cita — Clínica Dental Smile",
    "reschedule": "Cita reprogramada — Clínica Dental Smile",
    "cancellation": "Cancelación de su cita — Clínica Dental Smile",
}


def _selected_links(
    service: str, date: str, time: str, tz_name: str, clinic_name: str, recipient_email: str
) -> dict[str, str]:
    """Calendar links filtered to the recipient's provider (empty if no valid date/time)."""
    return select_links_for_email(
        recipient_email, build_calendar_links(service, date, time, tz_name, clinic_name)
    )


def _build_body(
    operation: str,
    name: str,
    service: str,
    date: str,
    time: str,
    tz_name: str = "Europe/Madrid",
    clinic_name: str = "Clínica Dental Smile",
    recipient_email: str = "",
) -> str:
    greeting = f"Hola {name}," if name else "Hola,"
    when = " ".join(p for p in (f"el {date}" if date else "", f"a las {time}" if time else "") if p)
    # Service name is shown in UPPERCASE in the email.
    svc = service.strip().upper() if service and service.strip() else "su cita"
    if operation == "cancellation":
        detail = f"Le confirmamos que su cita de {svc} {when} ha sido CANCELADA."
    elif operation == "reschedule":
        detail = f"Su cita ha sido reprogramada: {svc} {when}."
    else:
        detail = f"Le confirmamos su cita: {svc} {when}."

    # "Add to calendar" links — only for an upcoming appointment, and only the link
    # matching the recipient's email provider (both if it's a custom/unknown domain).
    calendar = ""
    if operation in ("booking", "reschedule"):
        links = _selected_links(service, date, time, tz_name, clinic_name, recipient_email)
        if links:
            lines = ["\n\nAñada la cita a su calendario:"]
            if "google" in links:
                lines.append(f"• Google Calendar: {links['google']}")
            if "outlook" in links:
                lines.append(f"• Outlook: {links['outlook']}")
            calendar = "\n".join(lines) + "\n"

    return (
        f"{greeting}\n\n{detail}{calendar}\n\n"
        f"Gracias por confiar en la {clinic_name}. Si necesita cualquier cambio, "
        "llámenos y estaremos encantados de ayudarle.\n\n"
        f"Un saludo,\n{clinic_name}"
    )


def _button(url: str, text: str, color: str) -> str:
    # The clickable <a> MUST live INSIDE the cells: Gmail strips an <a> that WRAPS a
    # <table>, leaving the button with no link at all. Each cell holds a block-level
    # link (padding inside it, so the whole cell is clickable); the colour + rounded
    # corners sit on the <td>, and td valign=middle keeps icon/label/arrow centred.
    href = escape(url, quote=True)
    link = "display:block;text-decoration:none;color:#ffffff;cursor:pointer;"
    return (
        '<table role="presentation" border="0" cellpadding="0" cellspacing="0" '
        'style="border-collapse:separate;margin:6px 0;">'
        "<tr>"
        f'<td style="background:{color};border-radius:6px 0 0 6px;vertical-align:middle;">'
        f'<a href="{href}" style="{link}padding:12px 0 12px 18px;font-size:18px;line-height:1;">📅</a></td>'
        f'<td style="background:{color};vertical-align:middle;">'
        f'<a href="{href}" style="{link}padding:12px 14px;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:15px;font-weight:bold;white-space:nowrap;">{escape(text)}</a></td>'
        f'<td style="background:{color};border-radius:0 6px 6px 0;vertical-align:middle;">'
        f'<a href="{href}" style="{link}padding:12px 20px 12px 0;font-size:22px;font-weight:bold;'
        f'line-height:1;">&#10132;</a></td>'
        "</tr></table>"
    )


def _build_html(
    operation: str,
    name: str,
    service: str,
    date: str,
    time: str,
    tz_name: str = "Europe/Madrid",
    clinic_name: str = "Clínica Dental Smile",
    recipient_email: str = "",
) -> str:
    greeting = f"Hola {escape(name)}," if name else "Hola,"
    when = " ".join(p for p in (f"el {escape(date)}" if date else "", f"a las {escape(time)}" if time else "") if p)
    svc = f"<strong>{escape(service.strip().upper())}</strong>" if service and service.strip() else "su cita"
    if operation == "cancellation":
        detail = f"Le confirmamos que su cita de {svc} {when} ha sido <strong>CANCELADA</strong>."
    elif operation == "reschedule":
        detail = f"Su cita ha sido reprogramada: {svc} {when}."
    else:
        detail = f"Le confirmamos su cita: {svc} {when}."

    buttons = ""
    if operation in ("booking", "reschedule"):
        links = _selected_links(service, date, time, tz_name, clinic_name, recipient_email)
        btns = []
        if "google" in links:
            btns.append(_button(links["google"], "Añadir a Google Calendar", "#1a73e8"))
        if "outlook" in links:
            btns.append(_button(links["outlook"], "Añadir a Outlook", "#0078d4"))
        if btns:
            buttons = (
                '<p style="margin:24px 0 8px;color:#1a1a1a;">Añada la cita a su calendario:</p>'
                + "<p style=\"margin:0;\">" + "<br>".join(btns) + "</p>"
            )

    clinic = escape(clinic_name)
    return (
        '<!DOCTYPE html><html><body style="margin:0;padding:0;background:#f4f6f8;">'
        '<div style="max-width:520px;margin:0 auto;padding:24px;'
        'font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;font-size:15px;line-height:1.5;">'
        f"<p>{greeting}</p><p>{detail}</p>{buttons}"
        f'<p style="color:#666;margin-top:24px;">Gracias por confiar en la {clinic}. '
        "Si necesita cualquier cambio, llámenos y estaremos encantados de ayudarle.</p>"
        f'<p style="color:#666;">Un saludo,<br>{clinic}</p>'
        "</div></body></html>"
    )


def make_tool(
    email_service: EmailService,
    supabase=None,
    phone: str = "",
    patient_name_default: str = "",
    tz_name: str = "Europe/Madrid",
    clinic_name: str = "Clínica Dental Smile",
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
        name = patient_name or patient_name_default
        body = _build_body(op, name, service, date, time, tz_name, clinic_name, recipient_email=email)
        html = _build_html(op, name, service, date, time, tz_name, clinic_name, recipient_email=email)
        try:
            await email_service.send(email, subject, body, html=html)
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
