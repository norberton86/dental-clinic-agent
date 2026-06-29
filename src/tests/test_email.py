import asyncio
import json

import pytest

from src.tools import send_appointment_email


PHONE = "+34600000000"


async def _drain():
    """Let the fire-and-forget send/persist background tasks finish before asserting."""
    if send_appointment_email._bg_tasks:
        await asyncio.gather(*list(send_appointment_email._bg_tasks))


class FakeEmail:
    """Records sends; can be 'unconfigured' or made to raise."""

    def __init__(self, configured: bool = True, error: Exception | None = None):
        self._configured = configured
        self._error = error
        self.sent: list[tuple[str, str, str]] = []
        self.html: list[str | None] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def send(self, to: str, subject: str, body: str, html: str | None = None) -> None:
        if self._error:
            raise self._error
        self.sent.append((to, subject, body))
        self.html.append(html)


class FakeSupabase:
    """Records RPC calls; can be made to raise."""

    def __init__(self, error: Exception | None = None):
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def rpc(self, fn: str, payload: dict):
        self.calls.append((fn, payload))
        if self._error:
            raise self._error
        return [{"patient_id": 1, "email": payload.get("p_email")}]


@pytest.mark.asyncio
async def test_send_is_non_blocking():
    # the tool returns immediately; the actual send happens in the background
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(await tool.coroutine(email="a@b.com", operation="booking"))
    assert out["status"] == "success"
    assert svc.sent == []          # not sent yet — backgrounded
    await _drain()
    assert len(svc.sent) == 1      # completes after the background task runs


@pytest.mark.asyncio
async def test_sends_valid_booking_email():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(
        await tool.coroutine(
            email="norberto@gmail.com", operation="booking",
            service="limpieza", date="2026-07-01", time="09:30", patient_name="Norberto",
        )
    )
    assert out["status"] == "success"
    await _drain()
    assert len(svc.sent) == 1
    to, subject, body = svc.sent[0]
    assert to == "norberto@gmail.com"
    assert "Confirmación" in subject
    assert "LIMPIEZA" in body and "Norberto" in body  # service shown uppercase


@pytest.mark.asyncio
async def test_rejects_invalid_email_without_sending():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(await tool.coroutine(email="norberto-at-gmail", operation="booking"))
    assert out["status"] == "error"
    await _drain()
    assert svc.sent == []  # never attempted (validated synchronously, no background task)


@pytest.mark.asyncio
async def test_unconfigured_service_reports_error():
    svc = FakeEmail(configured=False)
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(await tool.coroutine(email="a@b.com", operation="cancellation"))
    assert out["status"] == "error"
    await _drain()
    assert svc.sent == []


@pytest.mark.asyncio
async def test_send_failure_is_swallowed_in_background():
    # fire-and-forget: the tool returns success immediately; a send failure is logged
    # in the background, NOT surfaced mid-call.
    svc = FakeEmail(error=RuntimeError("smtp timeout"))
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(await tool.coroutine(email="a@b.com", operation="reschedule"))
    assert out["status"] == "success"
    await _drain()
    assert svc.sent == []  # send raised → nothing recorded, but call wasn't blocked


@pytest.mark.asyncio
async def test_cancellation_subject_and_body():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="a@b.com", operation="cancellation", service="extracción", date="2026-07-02", time="10:00")
    await _drain()
    _, subject, body = svc.sent[0]
    assert "Cancelación" in subject
    assert "CANCELADA" in body


@pytest.mark.asyncio
async def test_persists_email_to_patient_record_after_send():
    svc = FakeEmail()
    sb = FakeSupabase()
    tool = send_appointment_email.make_tool(svc, sb, PHONE)
    out = json.loads(await tool.coroutine(email="nuevo@gmail.com", operation="booking"))
    assert out["status"] == "success"
    await _drain()
    assert sb.calls == [("update_patient_email", {"p_phone": PHONE, "p_email": "nuevo@gmail.com"})]


@pytest.mark.asyncio
async def test_persist_failure_does_not_fail_the_sent_email():
    svc = FakeEmail()
    sb = FakeSupabase(error=RuntimeError("db down"))
    tool = send_appointment_email.make_tool(svc, sb, PHONE)
    out = json.loads(await tool.coroutine(email="ok@gmail.com", operation="booking"))
    assert out["status"] == "success"  # returns immediately
    await _drain()
    assert svc.sent and svc.sent[0][0] == "ok@gmail.com"  # email sent; persist failure swallowed


@pytest.mark.asyncio
async def test_booking_email_includes_calendar_links():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="a@b.com", operation="booking", service="limpieza", date="2026-07-01", time="09:30")
    await _drain()
    _, _, body = svc.sent[0]
    assert "calendar.google.com/calendar/render" in body
    assert "outlook.office.com" in body


@pytest.mark.asyncio
async def test_html_part_has_calendar_button():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="p@gmail.com", operation="booking", service="limpieza", date="2026-07-01", time="09:30")
    await _drain()
    html = svc.html[0]
    assert html is not None
    assert "Añadir a Google Calendar" in html
    assert "vertical-align:middle" in html and "&#10132;" in html
    assert 'href="https://calendar.google.com' in html
    assert "outlook" not in html.lower()


@pytest.mark.asyncio
async def test_gmail_recipient_gets_only_google_link():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="p@gmail.com", operation="booking", service="limpieza", date="2026-07-01", time="09:30")
    await _drain()
    _, _, body = svc.sent[0]
    assert "calendar.google.com" in body and "outlook.office.com" not in body


@pytest.mark.asyncio
async def test_outlook_recipient_gets_only_outlook_link():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="p@outlook.com", operation="booking", service="limpieza", date="2026-07-01", time="09:30")
    await _drain()
    _, _, body = svc.sent[0]
    assert "outlook.office.com" in body and "calendar.google.com" not in body


@pytest.mark.asyncio
async def test_custom_domain_gets_both_links():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="p@miclinica.com", operation="booking", service="limpieza", date="2026-07-01", time="09:30")
    await _drain()
    _, _, body = svc.sent[0]
    assert "calendar.google.com" in body and "outlook.office.com" in body


@pytest.mark.asyncio
async def test_cancellation_email_has_no_calendar_links():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="a@b.com", operation="cancellation", service="extracción", date="2026-07-01", time="09:30")
    await _drain()
    _, _, body = svc.sent[0]
    assert "calendar.google.com" not in body and "outlook.office.com" not in body


@pytest.mark.asyncio
async def test_invalid_email_does_not_persist():
    svc = FakeEmail()
    sb = FakeSupabase()
    tool = send_appointment_email.make_tool(svc, sb, PHONE)
    out = json.loads(await tool.coroutine(email="bad", operation="booking"))
    assert out["status"] == "error"
    await _drain()
    assert sb.calls == []  # nothing sent → nothing saved
