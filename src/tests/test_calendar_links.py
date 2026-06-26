from src.services.calendar_links import (
    build_calendar_links,
    provider_for_email,
    select_links_for_email,
)


def test_google_and_outlook_links_built_with_utc_times():
    # 09:30 Europe/Madrid in July = 07:30 UTC (CEST = UTC+2); limpieza = 30 min
    links = build_calendar_links("limpieza", "2026-07-01", "09:30", "Europe/Madrid", "Clínica Smile")
    assert set(links) == {"google", "outlook"}
    assert "calendar.google.com/calendar/render" in links["google"]
    assert "20260701T073000Z" in links["google"]  # start UTC
    assert "20260701T080000Z" in links["google"]  # +30 min
    assert "outlook.office.com" in links["outlook"]
    assert "2026-07-01T07%3A30%3A00Z" in links["outlook"] or "2026-07-01T07:30:00Z" in links["outlook"]


def test_duration_varies_by_service():
    # extracción = 45 min → end 08:15 UTC from 07:30 UTC
    g = build_calendar_links("extracción", "2026-07-01", "09:30", "Europe/Madrid")["google"]
    assert "20260701T081500Z" in g
    # blanqueamiento = 60 min → end 08:30 UTC
    g2 = build_calendar_links("blanqueamiento", "2026-07-01", "09:30", "Europe/Madrid")["google"]
    assert "20260701T083000Z" in g2


def test_service_name_uppercased_in_title():
    g = build_calendar_links("limpieza", "2026-07-01", "09:30")["google"]
    assert "LIMPIEZA" in g  # urlencoded title keeps letters


def test_missing_datetime_returns_empty():
    assert build_calendar_links("limpieza", "", "09:30") == {}
    assert build_calendar_links("limpieza", "2026-07-01", "") == {}


def test_invalid_date_returns_empty():
    assert build_calendar_links("limpieza", "not-a-date", "09:30") == {}


def test_provider_detection_by_domain():
    assert provider_for_email("a@gmail.com") == "google"
    assert provider_for_email("a@googlemail.com") == "google"
    assert provider_for_email("a@outlook.com") == "microsoft"
    assert provider_for_email("a@outlook.es") == "microsoft"
    assert provider_for_email("a@hotmail.co.uk") == "microsoft"
    assert provider_for_email("a@live.com") == "microsoft"
    assert provider_for_email("a@msn.com") == "microsoft"
    assert provider_for_email("a@miclinica.com") is None  # custom/Workspace → unknown
    assert provider_for_email("not-an-email") is None


def test_select_links_by_provider():
    links = {"google": "G", "outlook": "O"}
    assert set(select_links_for_email("x@gmail.com", links)) == {"google"}
    assert set(select_links_for_email("x@hotmail.com", links)) == {"outlook"}
    assert set(select_links_for_email("x@custom.org", links)) == {"google", "outlook"}
