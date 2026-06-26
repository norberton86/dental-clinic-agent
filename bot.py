"""Runner entry point for the dental-clinic voice agent.

Run:  uv run bot.py -t telnyx -x <your-public-host>

The Pipecat runner hosts the HTTP <Stream> webhook (POST /) and the media
WebSocket (/ws). `create_transport` parses the inbound call, builds the Telnyx
serializer, and exposes the parsed handshake on `runner_args.call_data` so we can
read the caller's number + call id for patient lookup and call-control tools.
"""
from __future__ import annotations

import logging

import structlog
from pipecat.pipeline.runner import PipelineRunner
from pipecat.runner.run import main
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams

from src.config.settings import get_settings
from src.graph.confirmation_gate import ConfirmationGate
from src.services.email_service import EmailService
from src.services.phone import normalize_phone
from src.services.supabase_client import SupabaseClient
from src.services.telnyx_client import TelnyxClient
from src.tools.registry import CallControl, CallSession
from src.transport.pipeline import build_pipeline_task

log = structlog.get_logger(__name__)


def _configure_logging(level: str) -> None:
    lvl = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=lvl, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(lvl),
    )


def _field(call_data: object, name: str) -> str:
    """Read a field from call_data whether it's a dict or a pydantic model."""
    if call_data is None:
        return ""
    if isinstance(call_data, dict):
        return str(call_data.get(name) or "")
    return str(getattr(call_data, name, "") or "")


async def bot(runner_args: RunnerArguments) -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)

    # The runner parses the inbound media WS, builds the Telnyx serializer, and
    # attaches the handshake to runner_args.call_data.
    transport_params = {
        "telnyx": lambda: FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
        ),
    }
    transport = await create_transport(runner_args, transport_params)

    call_data = getattr(runner_args, "call_data", None)
    call_control_id = _field(call_data, "call_id") or _field(call_data, "stream_id")
    caller_phone = normalize_phone(_field(call_data, "from_number"), settings.default_country_code)
    log.info("call.start", correlation_id=call_control_id, caller=caller_phone or "unknown")

    supabase = SupabaseClient(settings.supabase_url, settings.supabase_service_key)
    telnyx = TelnyxClient(settings.telnyx_api_key)
    email = EmailService(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        from_addr=settings.email_from,
        from_name=settings.email_from_name,
        use_tls=settings.smtp_use_tls,
    )
    session = CallSession(
        call_control_id=call_control_id,
        caller_phone=caller_phone,
        supabase=supabase,
        telnyx=telnyx,
        email=email,
        transfer_to=settings.human_transfer_number,
        gate=ConfirmationGate(),
        control=CallControl(),
    )

    task = build_pipeline_task(transport, session, settings)
    try:
        await PipelineRunner(handle_sigint=False).run(task)
    finally:
        await supabase.aclose()
        await telnyx.aclose()
        log.info("call.end", correlation_id=call_control_id)


if __name__ == "__main__":
    main()
