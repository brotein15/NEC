"""
Tests for core/transaction.py — Transaction dataclass and enumerations.
"""

import pytest
from datetime import datetime, timezone

from core.transaction import CardType, Transaction, TransactionStatus


class TestTransactionDefaults:
    """Transaction auto-generated fields are populated correctly."""

    def test_transaction_id_is_uuid4(self):
        import uuid
        txn = Transaction(
            terminal_id="T1", merchant_id="M1",
            card_last4="1234", card_type=CardType.VISA,
            amount=10.0, currency="USD",
        )
        # Should not raise
        uuid.UUID(txn.transaction_id, version=4)

    def test_timestamp_is_utc(self):
        txn = Transaction(
            terminal_id="T1", merchant_id="M1",
            card_last4="1234", card_type=CardType.VISA,
            amount=10.0, currency="USD",
        )
        assert txn.timestamp.tzinfo == timezone.utc

    def test_default_status_is_pending(self):
        txn = Transaction(
            terminal_id="T1", merchant_id="M1",
            card_last4="1234", card_type=CardType.VISA,
            amount=10.0, currency="USD",
        )
        assert txn.status == TransactionStatus.PENDING

    def test_default_auth_code_is_empty(self):
        txn = Transaction(
            terminal_id="T1", merchant_id="M1",
            card_last4="1234", card_type=CardType.VISA,
            amount=10.0, currency="USD",
        )
        assert txn.auth_code == ""

    def test_two_transactions_have_different_ids(self):
        t1 = Transaction(
            terminal_id="T1", merchant_id="M1",
            card_last4="1234", card_type=CardType.VISA,
            amount=10.0, currency="USD",
        )
        t2 = Transaction(
            terminal_id="T1", merchant_id="M1",
            card_last4="1234", card_type=CardType.VISA,
            amount=10.0, currency="USD",
        )
        assert t1.transaction_id != t2.transaction_id


class TestToSafeDict:
    """to_safe_dict() omits sensitive data."""

    def setup_method(self):
        self.txn = Transaction(
            terminal_id="TERM-1", merchant_id="MERCH-1",
            card_last4="4321", card_type=CardType.AMEX,
            amount=99.99, currency="EUR",
        )

    def test_safe_dict_contains_expected_keys(self):
        d = self.txn.to_safe_dict()
        for key in ("transaction_id", "terminal_id", "merchant_id", "card_last4",
                    "card_type", "amount", "currency", "timestamp", "status", "auth_code"):
            assert key in d, f"Missing key: {key}"

    def test_safe_dict_no_encrypted_payload(self):
        d = self.txn.to_safe_dict()
        assert "encrypted_payload" not in d

    def test_safe_dict_card_type_is_string(self):
        d = self.txn.to_safe_dict()
        assert isinstance(d["card_type"], str)

    def test_safe_dict_status_is_string(self):
        d = self.txn.to_safe_dict()
        assert isinstance(d["status"], str)


class TestCardTypeEnum:
    def test_all_supported_types(self):
        for value in ("VISA", "MC", "AMEX", "DISCOVER"):
            ct = CardType(value)
            assert ct.value == value


class TestTransactionStatusEnum:
    def test_all_statuses(self):
        for value in ("PENDING", "APPROVED", "DECLINED", "FAILED"):
            ts = TransactionStatus(value)
            assert ts.value == value
