import httpx
import pytest
import respx

from src.services.supabase_client import SupabaseClient, SupabaseError

URL = "https://example.supabase.co"
KEY = "service-key-123"


@respx.mock
@pytest.mark.asyncio
async def test_rpc_posts_to_correct_endpoint_with_headers():
    route = respx.post(f"{URL}/rest/v1/rpc/get_patient_by_phone").mock(
        return_value=httpx.Response(200, json=[{"patient_id": 1, "first_name": "Daily"}])
    )
    client = SupabaseClient(URL, KEY)
    try:
        data = await client.rpc("get_patient_by_phone", {"p_phone": "+34951840694"})
    finally:
        await client.aclose()

    assert data == [{"patient_id": 1, "first_name": "Daily"}]
    req = route.calls.last.request
    assert req.headers["apikey"] == KEY
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert b"+34951840694" in req.content


@respx.mock
@pytest.mark.asyncio
async def test_rpc_retries_on_500_then_succeeds():
    route = respx.post(f"{URL}/rest/v1/rpc/cancel_appointment").mock(
        side_effect=[
            httpx.Response(500, text="boom"),
            httpx.Response(200, json=[{"success": True}]),
        ]
    )
    client = SupabaseClient(URL, KEY)
    try:
        data = await client.rpc("cancel_appointment", {"p_phone": "+34951840694"})
    finally:
        await client.aclose()

    assert data == [{"success": True}]
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_rpc_4xx_raises_immediately():
    respx.post(f"{URL}/rest/v1/rpc/book_appointment_safe").mock(
        return_value=httpx.Response(400, text="bad request")
    )
    client = SupabaseClient(URL, KEY)
    try:
        with pytest.raises(SupabaseError):
            await client.rpc("book_appointment_safe", {"p_phone": "x"})
    finally:
        await client.aclose()


def test_requires_url_and_key():
    with pytest.raises(ValueError):
        SupabaseClient("", "")
