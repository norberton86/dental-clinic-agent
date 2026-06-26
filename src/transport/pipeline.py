"""Assemble the Pipecat pipeline for one call."""
from __future__ import annotations

import structlog
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions

from ..config.settings import Settings
from ..graph.agent import build_graph, make_llm
from ..prompts.system_prompt import build_system_prompt
from ..tools.registry import CallSession, build_tools
from .langgraph_processor import LangGraphProcessor
from .tts_factory import create_tts

log = structlog.get_logger(__name__)

_TELNYX_SAMPLE_RATE = 8000  # Telnyx media streams are 8 kHz PCMU


def build_pipeline_task(transport, session: CallSession, settings: Settings) -> PipelineTask:
    stt = DeepgramSTTService(
        api_key=settings.deepgram_api_key,
        live_options=LiveOptions(
            model=settings.deepgram_model,        # nova-3
            language=settings.deepgram_language,  # "es"
            smart_format=True,
            punctuate=True,
            interim_results=True,                 # lets VAD/endpointing fire promptly
        ),
    )

    system_prompt = build_system_prompt(session.caller_phone)
    llm = make_llm(settings)
    tools = build_tools(session)
    # Anthropic needs explicit cache_control markers; OpenAI/Telnyx cache automatically.
    graph = build_graph(
        llm, tools, system_prompt, cache_system=(settings.llm_provider == "anthropic")
    )

    agent_processor = LangGraphProcessor(
        graph,
        thread_id=session.call_control_id,
        gate=session.gate,
        telnyx=session.telnyx,
        control=session.control,
    )
    tts = create_tts(settings)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            agent_processor,
            tts,
            transport.output(),
        ]
    )

    # Pipecat 1.4.0 enables interruptions/barge-in by default (driven by STT speech
    # events); there is no allow_interruptions knob on PipelineParams anymore.
    return PipelineTask(pipeline, params=PipelineParams())
