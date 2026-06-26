"""Build "Add to calendar" links (Google / Outlook) for an appointment.

These are plain URLs the patient clicks to add the event to their OWN calendar —
no access to their account is needed or used. Times are anchored to the clinic's
timezone and emitted in UTC so they're unambiguous in any client.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")

# Consumer domains we can confidently attribute to a provider. Custom/Workspace
# domains are indistinguishable by name → treated as "unknown" (send both).
_GOOGLE_DOMAINS = {"gmail.com", "googlemail.com"}
_MICROSOFT_EXACT = {"msn.com", "passport.com", "live.com", "outlook.com", "hotmail.com"}
_MICROSOFT_PREFIXES = ("outlook.", "hotmail.", "live.")  # covers country variants (outlook.es, hotmail.co.uk…)


def provider_for_email(email: str) -> str | None:
    """Return 'google', 'microsoft', or None (unknown) based on the email domain."""
    if "@" not in (email or ""):
        return None
    domain = email.rsplit("@", 1)[-1].strip().lower()
    if domain in _GOOGLE_DOMAINS:
        return "google"
    if domain in _MICROSOFT_EXACT or domain.startswith(_MICROSOFT_PREFIXES):
        return "microsoft"
    return None


def select_links_for_email(email: str, links: dict[str, str]) -> dict[str, str]:
    """Keep only the calendar link matching the recipient's provider; both if unknown."""
    provider = provider_for_email(email)
    if provider == "google":
        return {k: v for k, v in links.items() if k == "google"}
    if provider == "microsoft":
        return {k: v for k, v in links.items() if k == "outlook"}
    return dict(links)

# Appointment duration (minutes) by Spanish service keyword — matches the prompt.
_DURATIONS = {
    "limpieza": 30,
    "blanqueamiento": 60,
    "extracción": 45,
    "extraccion": 45,
}
_DEFAULT_DURATION = 30


def _duration_minutes(service: str) -> int:
    s = (service or "").lower()
    for keyword, minutes in _DURATIONS.items():
        if keyword in s:
            return minutes
    return _DEFAULT_DURATION


def build_calendar_links(
    service: str,
    date: str,
    time: str,
    tz_name: str = "Europe/Madrid",
    clinic_name: str = "Clínica Dental Smile",
    location: str | None = None,
) -> dict[str, str]:
    """Return {"google": url, "outlook": url}, or {} if date/time are missing/invalid."""
    if not date or not time:
        return {}
    try:
        tz = ZoneInfo(tz_name)
        start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    except Exception:
        return {}

    end = start + timedelta(minutes=_duration_minutes(service))
    start_utc, end_utc = start.astimezone(_UTC), end.astimezone(_UTC)

    title = f"Cita dental — {service.strip().upper()}" if service.strip() else "Cita dental"
    loc = location or clinic_name
    details = f"Su cita en {clinic_name}."

    google = "https://calendar.google.com/calendar/render?" + urlencode(
        {
            "action": "TEMPLATE",
            "text": title,
            "dates": f"{start_utc:%Y%m%dT%H%M%SZ}/{end_utc:%Y%m%dT%H%M%SZ}",
            "details": details,
            "location": loc,
        }
    )
    outlook = "https://outlook.office.com/calendar/0/deeplink/compose?" + urlencode(
        {
            "path": "/calendar/action/compose",
            "rru": "addevent",
            "subject": title,
            "startdt": f"{start_utc:%Y-%m-%dT%H:%M:%SZ}",
            "enddt": f"{end_utc:%Y-%m-%dT%H:%M:%SZ}",
            "body": details,
            "location": loc,
        }
    )
    return {"google": google, "outlook": outlook}
