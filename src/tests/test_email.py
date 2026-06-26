import json

import pytest

from src.tools import send_appointment_email


class FakeEmail:
    """Records sends; can be 'unconfigured' or made to raise."""

    def __init__(self, configured: bool = True, error: Exception | None = None):
        self._configured = configured
        self._error = error
        self.sent: list[tuple[str, str, str]] = []

    @property
    def configured(self) -> bool:
        return self._configured

    async def send(self, to: str, subject: str, body: str) -> None:
        if self._error:
            raise self._error
        self.sent.append((to, subject, body))


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
    assert len(svc.sent) == 1
    to, subject, body = svc.sent[0]
    assert to == "norberto@gmail.com"
    assert "Confirmación" in subject
    assert "limpieza" in body and "Norberto" in body


@pytest.mark.asyncio
async def test_rejects_invalid_email_without_sending():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(await tool.coroutine(email="norberto-at-gmail", operation="booking"))
    assert out["status"] == "error"
    assert svc.sent == []  # never attempted


@pytest.mark.asyncio
async def test_unconfigured_service_reports_error():
    svc = FakeEmail(configured=False)
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(await tool.coroutine(email="a@b.com", operation="cancellation"))
    assert out["status"] == "error"
    assert svc.sent == []


@pytest.mark.asyncio
async def test_send_failure_returns_error_envelope():
    svc = FakeEmail(error=RuntimeError("smtp timeout"))
    tool = send_appointment_email.make_tool(svc)
    out = json.loads(await tool.coroutine(email="a@b.com", operation="reschedule"))
    assert out["status"] == "error"
    assert "smtp timeout" in out["message"]


@pytest.mark.asyncio
async def test_cancellation_subject_and_body():
    svc = FakeEmail()
    tool = send_appointment_email.make_tool(svc)
    await tool.coroutine(email="a@b.com", operation="cancellation", service="extracción", date="2026-07-02", time="10:00")
    _, subject, body = svc.sent[0]
    assert "Cancelación" in subject
    assert "CANCELADA" in body
