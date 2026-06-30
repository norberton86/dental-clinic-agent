"""Spanish date helpers.

The LLM is unreliable at computing the day-of-week for a date in its head (it has
mislabelled e.g. a Friday as "jueves"). So we compute weekday names here, from the
real calendar, and feed them to the agent — it should never derive a weekday itself.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

WEEKDAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def spanish_weekday(d: date | str) -> str | None:
    """Spanish weekday name for a date (or YYYY-MM-DD string). None if unparseable."""
    if isinstance(d, str):
        try:
            d = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    return WEEKDAYS_ES[d.weekday()]


def spanish_date_phrase(d: date | str) -> str | None:
    """Natural Spanish phrase, e.g. 'viernes 3 de julio'. None if unparseable."""
    if isinstance(d, str):
        try:
            d = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None
    return f"{WEEKDAYS_ES[d.weekday()]} {d.day} de {_MONTHS_ES[d.month - 1]}"


def upcoming_date_reference(today: date, days: int = 60) -> str:
    """A compact 'YYYY-MM-DD = weekday d de mes' line per day, today..today+days.
    Injected into the system prompt so the agent looks weekdays up instead of guessing."""
    lines = []
    for offset in range(days + 1):
        d = today + timedelta(days=offset)
        lines.append(f"{d.isoformat()} = {spanish_date_phrase(d)}")
    return "\n".join(lines)
