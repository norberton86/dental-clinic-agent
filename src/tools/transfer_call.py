from __future__ import annotations

from langchain_core.tools import StructuredTool

from ..models.schemas import EmptyArgs, ToolEnvelope


def make_tool(control, transfer_to: str) -> StructuredTool:
    async def _run() -> str:
        # Don't transfer immediately — that bridges the call away before the hand-off
        # line is heard. Just request it; the processor performs the Telnyx transfer
        # after the announcement finishes playing.
        if not transfer_to:
            return ToolEnvelope.fail("No human transfer number configured").to_tool_string()
        control.transfer_requested = True
        control.transfer_to = transfer_to
        return ToolEnvelope.ok(
            message="Transferencia en curso. El sistema dice «Un momento» y pasa la "
            "llamada automáticamente. NO diga nada más."
        ).to_tool_string()

    return StructuredTool.from_function(
        coroutine=_run,
        name="transfer_call",
        description=(
            "Transfer the current call to a human colleague. Use when the caller explicitly asks "
            "for a person/agent/receptionist, or when you genuinely cannot help. Say a brief "
            "hand-off line in Spanish in the SAME reply as calling this — the system plays the "
            "announcement first, then transfers."
        ),
        args_schema=EmptyArgs,
    )
