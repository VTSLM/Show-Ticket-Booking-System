import pytest
from fastapi import HTTPException

from routers.venue_verification import validate_decision


def test_approved_case_cannot_be_rejected_directly():
    # Decisions only accept these values; the API additionally requires the
    # current case status to be in_review before any decision can be made.
    validate_decision("approved", None)
    with pytest.raises(HTTPException) as exc:
        validate_decision("rejected", None)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("decision", ["rejected", "changes_requested"])
def test_negative_decisions_require_a_reason(decision):
    with pytest.raises(HTTPException) as exc:
        validate_decision(decision, "  ")
    assert exc.value.status_code == 422


def test_rejection_with_reason_is_valid():
    validate_decision("rejected", "Licence document is expired")


def test_request_changes_with_reason_is_valid():
    validate_decision("changes_requested", "Please provide a current NOC")