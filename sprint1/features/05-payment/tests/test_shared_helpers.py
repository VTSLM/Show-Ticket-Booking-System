"""Unit tests for shared-mode helpers; no external DB or Razorpay account needed."""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from backend.shared_main import amount_to_paise, money, provider_created_at, select_provider_payment


class SharedPaymentHelpersTests(unittest.TestCase):
    def test_amount_conversion_uses_rupees_as_decimal(self):
        self.assertEqual(amount_to_paise("675.40"), 67540)
        self.assertEqual(amount_to_paise("0.01"), 1)

    def test_money_format(self):
        self.assertEqual(money("675.4"), "₹675.40")

    def test_reconciliation_prefers_captured_attempt_for_order(self):
        attempts = [
            {"id": "pay_failed", "order_id": "order_123", "status": "failed", "created_at": 10},
            {"id": "pay_captured", "order_id": "order_123", "status": "captured", "created_at": 20},
            {"id": "pay_other", "order_id": "order_else", "status": "captured", "created_at": 30},
        ]
        self.assertEqual(select_provider_payment(attempts, "order_123")["id"], "pay_captured")

    def test_provider_timestamp_is_utc_aware(self):
        value = provider_created_at({"created_at": 1_700_000_000})
        self.assertIsNotNone(value)
        self.assertIsNotNone(value.tzinfo)


if __name__ == "__main__":
    unittest.main()
