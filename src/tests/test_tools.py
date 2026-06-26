import json
from datetime import date, timedelta

import pytest

from src.graph.confirmation_gate import ConfirmationGate
from src.services.supabase_client import SupabaseError
from src.tools import (
    book_appointment_safe,
    cancel_appointment,
    get_patient_by_phone,
    reschedule_appointment_safe,
)

PHONE = "+34951840694"
FUTURE = (date.today() + timedelta(days=10)).isoformat()


class FakeSupabase:
    """Records RPC calls and returns canned data (or raises)."""

    def __init__(self, result=None, error: str | None = None):
        self.result = result if result is not None else []
        self.error = error
        self.calls: list[tuple[str, dict]] = []

    async def rpc(self, fn: str, payload: dict):
        self.calls.append((fn, payload))
        if self.error:
            raise SupabaseError(self.error)
        return self.result


@pytest.mark.asyncio
async def test_get_patient_success_envelope():
    sb = FakeSupabase(result=[{"patient_id": 7, "first_name": "Daily"}])
    tool = get_patient_by_phone.make_tool(sb, PHONE)
    out = json.loads(await tool.coroutine())
    assert out["status"] == "success"
    assert out["data"][0]["first_name"] == "Daily"
    assert sb.calls == [("get_patient_by_phone", {"p_phone": PHONE})]


@pytest.mark.asyncio
async def test_book_held_until_confirmed_then_passes_args():
    sb = FakeSupabase(result=[{"success": True}])
    gate = ConfirmationGate()
    tool = book_appointment_safe.make_tool(sb, PHONE, gate)

    # caller just picked a time → gate HOLDS, nothing hits the DB
    gate.begin_user_turn("a las nueve y media")
    out1 = json.loads(await tool.coroutine(service_name="Cleaning", date=FUTURE, time="09:30"))
    assert out1["status"] == "pending"
    assert sb.calls == []

    # caller explicitly confirms → executes with the right payload
    gate.begin_user_turn("sí, es correcto")
    out2 = json.loads(await tool.coroutine(service_name="Cleaning", date=FUTURE, time="09:30"))
    assert out2["status"] == "success"
    assert sb.calls[-1] == (
        "book_appointment_safe",
        {"p_phone": PHONE, "p_service_name": "Cleaning", "p_date": FUTURE, "p_time": "09:30"},
    )


@pytest.mark.asyncio
async def test_book_rejects_past_date_without_db_call():
    sb = FakeSupabase()
    gate = ConfirmationGate()
    tool = book_appointment_safe.make_tool(sb, PHONE, gate)
    gate.begin_user_turn("sí")
    out = json.loads(await tool.coroutine(service_name="Cleaning", date="2020-01-01", time="09:30"))
    assert out["status"] == "error"
    assert sb.calls == []  # the gate blocked it before any DB write


@pytest.mark.asyncio
async def test_cancel_error_envelope_after_confirm():
    sb = FakeSupabase(error="network down")
    gate = ConfirmationGate()
    tool = cancel_appointment.make_tool(sb, PHONE, gate)
    await tool.coroutine()  # first call → pending
    gate.begin_user_turn("sí, cancélela")
    out = json.loads(await tool.coroutine())
    assert out["status"] == "error"
    assert "network down" in out["message"]


@pytest.mark.asyncio
async def test_reschedule_service_change_omitted_then_included():
    sb = FakeSupabase(result=[{"success": True}])
    gate = ConfirmationGate()
    tool = reschedule_appointment_safe.make_tool(sb, PHONE, gate)

    await tool.coroutine(new_date=FUTURE, new_time="10:00")  # pending
    gate.begin_user_turn("correcto")
    await tool.coroutine(new_date=FUTURE, new_time="10:00")  # execute
    assert "p_new_service_name" not in sb.calls[-1][1]

    gate.begin_user_turn("quiero blanqueamiento")  # new proposal → pending again
    await tool.coroutine(new_date=FUTURE, new_time="10:00", new_service_name="Whitening")
    gate.begin_user_turn("sí, es correcto")
    await tool.coroutine(new_date=FUTURE, new_time="10:00", new_service_name="Whitening")
    assert sb.calls[-1][1]["p_new_service_name"] == "Whitening"
