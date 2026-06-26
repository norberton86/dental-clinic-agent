from src.services.phone import normalize_phone


def test_already_e164_spain():
    assert normalize_phone("+34951840694") == "+34951840694"


def test_e164_with_spaces_and_dashes():
    assert normalize_phone("+34 951-840-694") == "+34951840694"


def test_spain_national_9_digits():
    assert normalize_phone("951840694", default_cc="+34") == "+34951840694"


def test_double_zero_international_prefix():
    assert normalize_phone("0034951840694") == "+34951840694"


def test_us_10_digit_when_default_us():
    assert normalize_phone("7862138423", default_cc="+1") == "+17862138423"


def test_us_11_digit_leading_one():
    assert normalize_phone("17862138423") == "+17862138423"


def test_us_e164_with_plus():
    assert normalize_phone("+1 (786) 213-8423") == "+17862138423"


def test_empty():
    assert normalize_phone("") == ""
    assert normalize_phone("   ") == ""


def test_fallback_uses_default_cc():
    # unrecognised length, not +-prefixed -> prepend default country code
    assert normalize_phone("12345", default_cc="+34") == "+3412345"
