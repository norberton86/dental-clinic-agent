from datetime import date

from src.utils.dates import spanish_date_phrase, spanish_weekday, upcoming_date_reference


def test_spanish_weekday_known_dates():
    # 2026-07-03 is a Friday (the date the model had mislabelled as "jueves").
    assert spanish_weekday("2026-07-03") == "viernes"
    assert spanish_weekday("2026-07-07") == "martes"
    assert spanish_weekday(date(2026, 6, 30)) == "martes"


def test_spanish_weekday_bad_input():
    assert spanish_weekday("not-a-date") is None
    assert spanish_weekday("") is None


def test_spanish_date_phrase():
    assert spanish_date_phrase("2026-07-03") == "viernes 3 de julio"
    assert spanish_date_phrase("2026-12-01") == "martes 1 de diciembre"


def test_upcoming_reference_covers_range_and_today():
    ref = upcoming_date_reference(date(2026, 6, 30), days=60)
    lines = ref.splitlines()
    assert len(lines) == 61  # today + 60 days, inclusive
    assert lines[0] == "2026-06-30 = martes 30 de junio"
    assert "2026-07-03 = viernes 3 de julio" in ref
