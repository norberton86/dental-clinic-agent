"""Custom Pipecat processor that drives the LangGraph agent.

Responsibilities:
- On a FINAL user transcript, run the agent and stream ONLY the final spoken
  answer to TTS (tool-deciding turns emit no spoken text).
- On barge-in (interruption / user-started-speaking), cancel the in-flight run.
- On pipeline start, kick off the greeting so the bot speaks first (no menu).

NOTE: frame types here follow current Pipecat; if you pin a different version,
confirm the imported frame names. This is the most version-sensitive file.
"""
from __future__ import annotations

import asyncio
import time

import structlog
from langchain_core.messages import HumanMessage
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    CancelFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    StartFrame,
    TextFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    UserStartedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

log = structlog.get_logger(__name__)

# Sent as the first "user" turn so the agent greets and identifies the caller.
GREETING_NUDGE = (
    "(El sistema indica: llamada entrante iniciada. Saluda brevemente en español como la "
    "recepción de la Clínica Dental Smile e identifica al paciente por su teléfono.)"
)
_ERROR_LINE = "Lo siento, ha habido un problema. ¿Puede repetir, por favor?"
# Fixed hand-off line spoken on any transfer turn — short and consistent, so the
# call isn't held up by the model's (often long, doubled) transfer narration.
_TRANSFER_LINE = "Un momento."


def _usage_from_event(event) -> tuple[int, int, int]:
    """(input, output, cached) tokens from an on_chat_model_end event; 0s if absent.
    Works across providers — usage_metadata is normalized by LangChain."""
    out = (event.get("data") or {}).get("output")
    um = getattr(out, "usage_metadata", None)
    if um is None and out is not None:
        um = getattr(getattr(out, "message", None), "usage_metadata", None)
    if not um:
        return (0, 0, 0)
    cached = (um.get("input_token_details") or {}).get("cache_read", 0) or 0
    return (um.get("input_tokens", 0) or 0, um.get("output_tokens", 0) or 0, cached)


def _chunk_text(chunk) -> str:
    """Extract text from an AIMessageChunk (str content, or list of blocks)."""
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return ""


class LangGraphProcessor(FrameProcessor):
    def __init__(self, graph, thread_id: str, gate=None, telnyx=None, control=None) -> None:
        super().__init__()
        self._graph = graph
        self._config = {"configurable": {"thread_id": thread_id}}
        self._task: asyncio.Task | None = None
        self._correlation = thread_id
        self._gate = gate  # ConfirmationGate: told of each caller turn for the confirm gate
        self._telnyx = telnyx          # TelnyxClient for the deferred hangup
        self._call_control_id = thread_id
        self._control = control        # CallControl: end_requested set by hangup_call

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, StartFrame):
            await self.push_frame(frame, direction)
            await self._start_turn(GREETING_NUDGE)
            return

        if isinstance(frame, (InterruptionFrame, UserStartedSpeakingFrame)):
            await self._cancel_turn()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (EndFrame, CancelFrame)):
            await self._cancel_turn()
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                await self._start_turn(text)
            # consume final transcripts; do not forward downstream
            return

        # The spoken line has finished playing — now it's safe to act on a deferred
        # hangup or transfer (doing it earlier cuts off the goodbye / hand-off line).
        if isinstance(frame, BotStoppedSpeakingFrame):
            await self.push_frame(frame, direction)
            if self._control is not None and self._telnyx is not None:
                if self._control.transfer_requested:
                    self._control.transfer_requested = False
                    to = self._control.transfer_to
                    log.info(
                        "call.transfer_after_announce",
                        correlation_id=self._correlation,
                        to=to,
                    )
                    await self._telnyx.transfer(self._call_control_id, to)
                elif self._control.end_requested:
                    self._control.end_requested = False
                    log.info("call.hangup_after_goodbye", correlation_id=self._correlation)
                    await self._telnyx.hangup(self._call_control_id)
            return

        # everything else (interim transcripts, audio, control) flows through
        await self.push_frame(frame, direction)

    async def _cancel_turn(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

    async def _start_turn(self, user_text: str) -> None:
        await self._cancel_turn()
        # Tell the confirm-gate whether this caller turn is an affirmation BEFORE the
        # graph runs, so a mutating tool called this turn sees the right state.
        if self._gate is not None:
            self._gate.begin_user_turn(user_text)
        self._task = asyncio.create_task(self._run_turn(user_text))

    async def _run_turn(self, user_text: str) -> None:
        t0 = time.monotonic()
        log.info("turn.start", correlation_id=self._correlation, user=user_text[:120])
        await self.push_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        spoke_any = False
        buffer: list[str] = []
        spoken: set[str] = set()
        messages: list[str] = []
        # per-turn metrics (latency + tokens + hop counts)
        in_tok = out_tok = cached_tok = 0
        llm_calls = 0  # LLM round-trips this turn (hops = llm_calls - 1)
        tool_runs = 0  # tool executions this turn
        first_speak_t: float | None = None
        try:
            # Collect each DISTINCT message's text, then speak only the FINAL one.
            # In a ReAct turn the model frequently narrates alongside a tool call
            # (e.g. "¿A qué hora le viene bien?") and only the LAST message reflects
            # the tool result (e.g. "no hay disponibilidad"). Speaking the intermediate
            # ones produces duplicated or even CONTRADICTORY speech — only the final
            # assistant message is the real reply. This also covers the goodbye said in
            # the same message as hangup_call (it's the last non-empty message).
            async for event in self._graph.astream_events(
                {"messages": [HumanMessage(content=user_text)]},
                self._config,
                version="v2",
            ):
                ev = event.get("event")
                if ev == "on_chat_model_stream":
                    buffer.append(_chunk_text(event["data"]["chunk"]))
                elif ev == "on_chat_model_end":
                    llm_calls += 1
                    i, o, c = _usage_from_event(event)
                    in_tok += i
                    out_tok += o
                    cached_tok += c
                    text = "".join(buffer).strip()
                    buffer = []
                    if text and text not in spoken:
                        spoken.add(text)
                        messages.append(text)
                elif ev == "on_tool_end":
                    tool_runs += 1
            # Transfer turn → one fixed hand-off line (the processor transfers once it
            # finishes playing). Otherwise speak ONLY the final assistant message.
            if self._control is not None and self._control.transfer_requested:
                to_speak = [_TRANSFER_LINE]
            elif messages:
                to_speak = [messages[-1]]
            else:
                to_speak = []
            for text in to_speak:
                if first_speak_t is None:
                    first_speak_t = time.monotonic()
                spoke_any = True
                await self.push_frame(TextFrame(text), FrameDirection.DOWNSTREAM)
            log.info(
                "turn.metrics",
                correlation_id=self._correlation,
                total_s=round(time.monotonic() - t0, 2),
                ttf_audio_s=round(first_speak_t - t0, 2) if first_speak_t else None,
                llm_calls=llm_calls,       # round-trips (hops = llm_calls - 1)
                tool_runs=tool_runs,
                in_tok=in_tok,
                out_tok=out_tok,
                cached_tok=cached_tok,
                spoke=spoke_any,
            )
        except asyncio.CancelledError:
            log.info("turn.cancelled", correlation_id=self._correlation)
            await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
            raise
        except Exception as exc:  # noqa: BLE001 - keep the call alive
            log.error("turn.error", correlation_id=self._correlation, error=str(exc))
            await self.push_frame(TTSSpeakFrame(_ERROR_LINE), FrameDirection.DOWNSTREAM)
        await self.push_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
