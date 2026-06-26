"""Telnyx Call Control REST helpers: transfer + hangup.

These act on an existing call by its `call_control_id`. The runner owns call
bring-up (the <Stream> webhook), so there is no answer/streaming_start here.
"""
from __future__ import annotations

import httpx
import structlog

log = structlog.get_logger(__name__)

_BASE = "https://api.telnyx.com/v2"
_TIMEOUT = 10.0


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
            log.error("telnyx.transfer.error", error=str(exc))
            return False

    async def hangup(self, call_control_id: str) -> bool:
        """Hang up the active call."""
        url = f"{_BASE}/calls/{call_control_id}/actions/hangup"
        try:
            resp = await self._client.post(url, json={})
            ok = resp.status_code < 300
            log.info("telnyx.hangup", status=resp.status_code, ok=ok)
            return ok
        except httpx.HTTPError as exc:
            log.error("telnyx.hangup.error", error=str(exc))
            return False
