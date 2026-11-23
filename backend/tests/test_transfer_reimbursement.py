import json
from uuid import UUID

import httpx
import pytest

from services import transfer_reimbursement as service

REFERENCE = UUID("991b2849-54b7-4088-b13f-3eaf47dc1278")
INTENT = {
    "reference_id": str(REFERENCE),
    "amount": 100,
    "currency": "INR",
    "fund_account_id": "fa_testfund",
}
PAYOUT = {"id": "pout_test", **INTENT, "status": "processing"}


@pytest.fixture
def test_account(monkeypatch):
    monkeypatch.setenv("RAZORPAYX_TEST_KEY_ID", "rzp_test_example")
    monkeypatch.setenv("RAZORPAYX_TEST_KEY_SECRET", "test-secret")
    monkeypatch.setenv("RAZORPAYX_TEST_ACCOUNT_NUMBER", "123456789")
    monkeypatch.setenv("RAZORPAYX_TEST_FUND_ACCOUNT_ID", INTENT["fund_account_id"])


def mock_provider(monkeypatch, handler):
    client = httpx.Client
    monkeypatch.setattr(service.httpx, "Client",
                        lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def test_create_and_fetch_check_the_same_test_payout(test_account, monkeypatch):
    requests = []

    def provider(request):
        requests.append(request)
        payout = PAYOUT if request.method == "POST" else {**PAYOUT, "status": "processed"}
        return httpx.Response(200, json=payout)

    mock_provider(monkeypatch, provider)
    result = service.run_test_payout(REFERENCE, 100)
    assert result == {"test_mode": True, "payout_id": PAYOUT["id"], "provider_status": "processing"}
    assert service.run_test_payout(REFERENCE, 100, result["payout_id"])["provider_status"] == "processed"
    sent, checked = requests
    assert sent.headers["X-Payout-Idempotency"] == str(REFERENCE)
    assert json.loads(sent.content) == {
        **INTENT, "account_number": "123456789", "mode": "IMPS",
        "purpose": "payout", "queue_if_low_balance": False,
    }
    assert checked.method == "GET" and str(checked.url) == f"{service.PAYOUT_URL}/{PAYOUT['id']}"


def test_live_keys_are_refused_before_connection(test_account, monkeypatch):
    monkeypatch.setenv("RAZORPAYX_TEST_KEY_ID", "rzp_live_example")
    mock_provider(monkeypatch, lambda _: pytest.fail("Must refuse live credentials"))
    with pytest.raises(service.PayoutTestError, match="test-mode credentials"):
        service.run_test_payout(REFERENCE, 100)


@pytest.mark.parametrize("changed", [{"fund_account_id": "fa_other"}, {"amount": 200},
                                    {"currency": "USD"}, {"reference_id": "other"}])
def test_mismatched_processed_payout_is_rejected(test_account, monkeypatch, changed):
    mock_provider(monkeypatch, lambda _: httpx.Response(200, json={**PAYOUT, "status": "processed", **changed}))
    with pytest.raises(service.PayoutTestError, match="does not match"):
        service.run_test_payout(REFERENCE, 100, PAYOUT["id"])


def test_timeout_preserves_retry_reference(test_account, monkeypatch):
    def provider(request):
        assert request.headers["X-Payout-Idempotency"] == str(REFERENCE)
        raise httpx.ReadTimeout("No response")

    mock_provider(monkeypatch, provider)
    with pytest.raises(service.PayoutTestError, match="same reference and amount"):
        service.run_test_payout(REFERENCE, 100)
