import httpx
import pytest
import respx

from src.services.telnyx_client import TelnyxClient

HANGUP = "https://api.telnyx.com/v2/calls/cc-123/actions/hangup"


@respx.mock
@pytest.mark.asyncio
async def test_hangup_succeeds_first_try():
    route = respx.post(HANGUP).mock(return_value=httpx.Response(200, json={}))
    c = TelnyxClient("key")
    try:
        assert await c.hangup("cc-123") is True
    finally:
        await c.aclose()
    assert route.call_count == 1  # no needless retry


@respx.mock
@pytest.mark.asyncio
async def test_hangup_retries_then_succeeds():
    # attempt 1 times out, attempt 2 succeeds
    def handler(request):
        handler.n = getattr(handler, "n", 0) + 1
        if handler.n < 2:
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(200, json={})

    route = respx.post(HANGUP).mock(side_effect=handler)
    c = TelnyxClient("key")
    try:
        assert await c.hangup("cc-123") is True  # recovered via retry
    finally:
        await c.aclose()
    assert route.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_hangup_already_gone_is_success_no_retry():
    # 404 = the call already ended → the outcome we wanted; don't retry
    route = respx.post(HANGUP).mock(return_value=httpx.Response(404, json={}))
    c = TelnyxClient("key")
    try:
        assert await c.hangup("cc-123") is True
    finally:
        await c.aclose()
    assert route.call_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_hangup_exhausts_retries_then_false():
    def always_timeout(request):
        raise httpx.ConnectTimeout("timeout", request=request)

    route = respx.post(HANGUP).mock(side_effect=always_timeout)
    c = TelnyxClient("key")
    try:
        assert await c.hangup("cc-123") is False
    finally:
        await c.aclose()
    assert route.call_count == 3  # all attempts used


@respx.mock
@pytest.mark.asyncio
async def test_transfer_success_and_error():
    route = respx.post("https://api.telnyx.com/v2/calls/cc-1/actions/transfer").mock(
        return_value=httpx.Response(200, json={})
    )
    c = TelnyxClient("key")
    try:
        assert await c.transfer("cc-1", "+17867979763") is True
    finally:
        await c.aclose()
    assert route.call_count == 1
