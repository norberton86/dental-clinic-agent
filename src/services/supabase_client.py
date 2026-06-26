"""Shared async Supabase REST/RPC client with retry + timeout."""
from __future__ import annotations

import asyncio

import httpx
import structlog

log = structlog.get_logger(__name__)

_TIMEOUT_SECONDS = 10.0
_MAX_RETRIES = 2  # i.e. up to 3 attempts total


class SupabaseError(RuntimeError):
    """Raised when an RPC call ultimately fails (after retries)."""


class SupabaseClient:
    """Calls Supabase Postgres RPC functions over the REST endpoint.

    One shared instance per process (dependency-injected into the tools).
    """

    def __init__(self, url: str, service_key: str, *, timeout: float = _TIMEOUT_SECONDS) -> None:
        if not url or not service_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY are required")
        self._base = url.rstrip("/")
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.AsyncClient(timeout=timeout, headers=self._headers)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def rpc(self, fn: str, payload: dict) -> object:
        """POST {url}/rest/v1/rpc/{fn}; returns parsed JSON. Retries on transient errors."""
        endpoint = f"{self._base}/rest/v1/rpc/{fn}"
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await self._client.post(endpoint, json=payload)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"server error {resp.status_code}", request=resp.request, response=resp
                    )
                if resp.status_code >= 400:
                    # 4xx is not retryable — surface the body.
                    raise SupabaseError(f"{fn} -> HTTP {resp.status_code}: {resp.text[:300]}")
                return resp.json()
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    backoff = 0.4 * (2**attempt)
                    log.warning("supabase.rpc.retry", fn=fn, attempt=attempt + 1, backoff=backoff, error=str(exc))
                    await asyncio.sleep(backoff)
                    continue
                log.error("supabase.rpc.failed", fn=fn, error=str(exc))
                raise SupabaseError(f"{fn} failed after retries: {exc}") from exc
        raise SupabaseError(f"{fn} failed: {last_exc}")
