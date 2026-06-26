"""Code-enforced safety gate for the mutating tools (book / reschedule / cancel).

Two guarantees the model CANNOT bypass (validated against Kimi-K2.6 + Qwen):
  1. Field validation — reject missing/invalid/past dates, bad times, bad service
     (stops the model fabricating a date the caller never gave).
  2. Two-phase confirm — a mutating tool only executes if the caller affirmed a
     read-back in the immediately preceding turn for the SAME proposal.

The processor calls `begin_user_turn(text)` once per caller utterance so the gate
knows whether the caller just confirmed; the tools call `evaluate(...)`.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from ..models.schemas import SERVICES

_AFFIRM = re.compile(
    r"\b(s[ií]|correcto|vale|perfecto|exacto|eso es|de acuerdo|claro|adelante|confirmo)\b",
    re.IGNORECASE,
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

_HOLD_MSG = (
    "NO ejecutado todavía. Lea al paciente los datos completos (servicio, fecha y hora) "
    "y pregunte '¿Es correcto?'. Vuelva a llamar a esta función con los MISMOS argumentos "
    "solo cuando el paciente confirme."
)


def _valid_future_date(value, today: date) -> bool:
    if not (isinstance(value, str) and _DATE_RE.match(value)):
        return False
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() >= today
    except ValueError:
        return False


def _valid_time(value) -> bool:
    return isinstance(value, str) and bool(_TIME_RE.match(value))


class ConfirmationGate:
    """Per-call gate. One instance per CallSession (per thread/call)."""

    def __init__(self) -> None:
        self._affirmed: bool = False

    def begin_user_turn(self, text: str) -> None:
        """Record whether the caller's latest utterance is an affirmation."""
        self._affirmed = bool(_AFFIRM.search(text or ""))

    def evaluate(self, action: str, args: dict, today: date | None = None) -> tuple[str, str]:
        """Return (verdict, message). verdict in {"execute", "hold", "error"}.

        A mutating tool executes ONLY when (a) the args are valid AND (b) the caller's
        most recent utterance was an affirmation. If not affirmed, HOLD — the tool
        returns a "read the details back and ask ¿Es correcto?" instruction, so the
        mutation can't happen until the caller has explicitly confirmed.
        """
        today = today or date.today()
        err = self._validate(action, args, today)
        if err:
            return ("error", err)
        if self._affirmed:
            return ("execute", "")
        return ("hold", _HOLD_MSG)

    @staticmethod
    def _validate(action: str, args: dict, today: date) -> str | None:
        if action == "book":
            if args.get("service_name") not in SERVICES:
                return "Falta el servicio (limpieza, blanqueamiento o extracción)."
            if not _valid_future_date(args.get("date"), today):
                return "Falta una fecha válida y futura. Pregunte al paciente la fecha; NO la invente."
            if not _valid_time(args.get("time")):
                return "Falta una hora válida (HH:MM). Pregunte la hora."
        elif action == "reschedule":
            if not _valid_future_date(args.get("new_date"), today):
                return "Falta una fecha válida y futura. Pregunte la nueva fecha; NO la invente."
            if not _valid_time(args.get("new_time")):
                return "Falta una hora válida (HH:MM). Pregunte la hora."
        # cancel: no fields to validate, but two-phase confirm still applies
        return None
