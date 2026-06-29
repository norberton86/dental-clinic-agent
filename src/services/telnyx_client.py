"""Telnyx Call Control REST helpers: transfer + hangup.

These act on an existing call by its `call_control_id`. The runner owns call
bring-up (the <Stream> webhook), so there is no answer/streaming_start here.
"""
from __future__ import annotations

import asyncio

import httpx
import structlog

log = structlog.get_logger(__name__)

_BASE = "https://api.telnyx.com/v2"
_TIMEOUT = 4.0          # per-attempt (a single 10s timeout once left a call open)
_HANGUP_RETRIES = 3     # a transient timeout must NOT leave the caller on the line
_RETRY_BACKOFF = 0.3


class TelnyxClient:
    def __init__(self, api_key: str, *, timeout: float = _TIMEOUT) -> None:
        if not api_key:
            raise ValueError("TELNYX_API_KEY is required")
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def transfer(self, call_control_id: str, to: str) -> bool:
        """Transfer the active call to `to` (E.164)."""
        url = f"{_BASE}/calls/{call_control_id}/actions/transfer"
        try:
            resp = await self._client.post(url, json={"to": to})
            ok = resp.status_code < 300
            log.info("telnyx.transfer", to=to, status=resp.status_code, ok=ok)
            if not ok:
                log.error("telnyx.transfer.failed", body=resp.text[:300])
            return ok
        except httpx.HTTPError as exc:
            # include the exception TYPE — a bare str(timeout) is empty and unhelpful
            log.error("telnyx.transfer.error", error=f"{type(exc).__name__}: {exc}")
            return False

    async def hangup(self, call_control_id: str) -> bool:
        """Hang up the active call, with retries.

        A single timeout once left a call connected after the goodbye, so we retry.
        A 404/422 means the call is already gone — that's the outcome we wanted, so
        treat it as success and stop.
        """
        url = f"{_BASE}/calls/{call_control_id}/actions/hangup"
        for attempt in range(1, _HANGUP_RETRIES + 1):
            try:
                resp = await self._client.post(url, json={})
                if resp.status_code < 300:
                    log.info("telnyx.hangup", status=resp.status_code, ok=True, attempt=attempt)
                    return True
                if resp.status_code in (404, 422):
                    log.info("telnyx.hangup.already_gone", status=resp.status_code)
                    return True
                log.error(
                    "telnyx.hangup.failed",
                    status=resp.status_code,
                    attempt=attempt,
                    body=resp.text[:200],
                )
            except httpx.HTTPError as exc:
                log.error(
                    "telnyx.hangup.error", attempt=attempt, error=f"{type(exc).__name__}: {exc}"
                )
            if attempt < _HANGUP_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF)
        log.error("telnyx.hangup.gave_up", attempts=_HANGUP_RETRIES)
        return False
