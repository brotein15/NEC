"""
Tests for core/processor.py — PaymentProcessor.
"""

import pytest
from unittest.mock import patch

from core.processor import PaymentProcessor, ProcessingResult
from core.transaction import CardType, Transaction, TransactionStatus


def make_txn(**kwargs) -> Transaction:
    defaults = dict(
        terminal_id="TERM-001",
        merchant_id="MERCH-001",
        card_last4="1234",
        card_type=CardType.VISA,
        amount=100.0,
        currency="USD",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


class TestBlockedCard:
    def test_card_last4_0000_is_declined(self):
        proc = PaymentProcessor()
        result = proc.process(make_txn(card_last4="0000"))
        assert result.status == TransactionStatus.DECLINED
        assert "blocked" in result.message.lower()
        assert result.auth_code == ""
        assert result.fee == 0.0


class TestManualReviewThreshold:
    def test_amount_above_10000_is_declined(self):
        proc = PaymentProcessor()
        result = proc.process(make_txn(amount=10001.0))
        assert result.status == TransactionStatus.DECLINED
        assert "manual review" in result.message.lower()

    def test_amount_exactly_10000_is_not_declined_for_review(self):
        """Amounts exactly at the threshold should not trigger the manual-review rule."""
        proc = PaymentProcessor()
        # Patch random to never random-decline so we isolate this rule
        with patch("core.processor.random.random", return_value=0.5):
            result = proc.process(make_txn(amount=10000.0))
        # Must not have been declined due to manual review
        assert "manual review" not in result.message.lower()


class TestApproval:
    def test_normal_transaction_approved(self):
        proc = PaymentProcessor()
        # Force random.random to return a high value (no random decline)
        with patch("core.processor.random.random", return_value=0.5):
            result = proc.process(make_txn(amount=50.0))
        assert result.status == TransactionStatus.APPROVED
        assert result.auth_code != ""
        assert result.fee > 0

    def test_random_decline(self):
        proc = PaymentProcessor()
        # Force random.random to return a value below decline threshold
        with patch("core.processor.random.random", return_value=0.01):
            result = proc.process(make_txn(amount=50.0))
        assert result.status == TransactionStatus.DECLINED


class TestFeeCalculation:
    def test_fee_formula(self):
        """Fee = amount * 2.9% + $0.30"""
        proc = PaymentProcessor()
        amount = 100.0
        expected_fee = round(amount * 0.029 + 0.30, 2)
        with patch("core.processor.random.random", return_value=0.5):
            result = proc.process(make_txn(amount=amount))
        if result.status == TransactionStatus.APPROVED:
            assert result.fee == expected_fee

    def test_zero_fee_on_decline(self):
        proc = PaymentProcessor()
        result = proc.process(make_txn(card_last4="0000"))
        assert result.fee == 0.0

    def test_fee_rounding(self):
        proc = PaymentProcessor()
        # $9.99 → fee = 9.99 * 0.029 + 0.30 = 0.58971 → 0.59
        amount = 9.99
        expected = round(amount * 0.029 + 0.30, 2)
        assert proc._calculate_fee(amount) == expected
