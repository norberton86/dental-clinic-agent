"""Phone normalization to E.164 (configurable default country)."""
from __future__ import annotations

import re


def normalize_phone(phone: str, default_cc: str = "+34") -> str:
    """Normalize to E.164.

    Inbound Telnyx caller IDs already arrive +-prefixed; the fallbacks cover
    digits a caller might type/speak for an alternate number.
    """
    if phone is None:
        return ""
    raw = phone.strip()
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return ""
    if raw.startswith("+"):
        return f"+{digits}"
    if digits.startswith("00"):  # international 00 prefix
        return f"+{digits[2:]}"
    if len(digits) == 10 and default_cc == "+1":  # US 10-digit
        return f"+1{digits}"
    if len(digits) == 11 and digits[0] == "1":  # US 1XXXXXXXXXX
        return f"+{digits}"
    if len(digits) == 9 and default_cc == "+34":  # Spain national 9-digit
        return f"+34{digits}"
    return f"{default_cc}{digits}"
