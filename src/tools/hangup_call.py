from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs, ToolEnvelope


def make_tool(control) -> StructuredTool:
    async def _run() -> str:
        # Don't hang up immediately — that cuts off the goodbye. Just request the end;
        # the processor hangs up after the farewell finishes playing.
        control.end_requested = True
        return ToolEnvelope.ok(
            message="Despídase brevemente en español en esta misma respuesta; el sistema "
            "reproducirá la despedida y luego colgará."
        ).to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="hangup_call",
        description=(
            "End the call when the caller needs nothing more. Say a short goodbye in Spanish in "
            "the SAME reply as calling this — the system plays the farewell first, then hangs up."
        ),
        args_schema=EmptyArgs,
    )
