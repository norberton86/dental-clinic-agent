from datetime import date

from src.graph.confirmation_gate import ConfirmationGate

TODAY = date(2026, 6, 24)
FUT = "2026-07-06"


def test_holds_then_executes_only_after_affirmation():
    g = ConfirmationGate()
    args = {"service_name": "Cleaning", "date": FUT, "time": "09:30"}

    assert g.evaluate("book", args, today=TODAY)[0] == "hold"      # first proposal
    g.begin_user_turn("no, mejor otro día")                        # not an affirmation
    assert g.evaluate("book", args, today=TODAY)[0] == "hold"
    g.begin_user_turn("sí, es correcto")                           # affirmation
    assert g.evaluate("book", args, today=TODAY)[0] == "execute"


def test_rejects_past_date():
    g = ConfirmationGate()
    g.begin_user_turn("sí")
    v, msg = g.evaluate("book", {"service_name": "Cleaning", "date": "2020-01-01", "time": "09:30"}, today=TODAY)
    assert v == "error"
    assert "fecha" in msg.lower()


def test_rejects_missing_or_bad_fields():
    g = ConfirmationGate()
    assert g.evaluate("book", {"service_name": "Cleaning", "date": FUT}, today=TODAY)[0] == "error"  # no time
    assert g.evaluate("book", {"service_name": "Bogus", "date": FUT, "time": "09:30"}, today=TODAY)[0] == "error"
    assert g.evaluate("book", {"service_name": "Cleaning", "date": "tomorrow", "time": "09:30"}, today=TODAY)[0] == "error"


def test_valid_args_hold_until_caller_affirms():
    # Core property: valid args alone are NOT enough — the caller must have affirmed
    # this turn, else HOLD (so the agent reads back and asks before any mutation).
    g = ConfirmationGate()
    args = {"service_name": "Cleaning", "date": FUT, "time": "09:30"}
    assert g.evaluate("book", args, today=TODAY)[0] == "hold"      # no affirmation yet
    g.begin_user_turn("la primera opción que tenga")               # still not an affirmation
    assert g.evaluate("book", args, today=TODAY)[0] == "hold"


def test_cancel_requires_confirmation():
    g = ConfirmationGate()
    assert g.evaluate("cancel", {}, today=TODAY)[0] == "hold"
    g.begin_user_turn("sí, cancélela")
    assert g.evaluate("cancel", {}, today=TODAY)[0] == "execute"


def test_reschedule_validates_and_confirms():
    g = ConfirmationGate()
    # missing time → error
    assert g.evaluate("reschedule", {"new_date": FUT}, today=TODAY)[0] == "error"
    # valid → hold then execute
    args = {"new_date": FUT, "new_time": "10:00", "new_service_name": "Whitening"}
    assert g.evaluate("reschedule", args, today=TODAY)[0] == "hold"
    g.begin_user_turn("correcto")
    assert g.evaluate("reschedule", args, today=TODAY)[0] == "execute"
