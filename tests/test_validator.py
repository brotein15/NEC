"""
Tests for core/validator.py — TransactionValidator.
"""

import pytest

from core.transaction import CardType, Transaction, TransactionStatus
from core.validator import TransactionValidator, ValidationError


def make_txn(**kwargs) -> Transaction:
    """Helper: build a valid transaction overriding specific fields."""
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


class TestAmountValidation:
    def test_valid_amount_passes(self):
        v = TransactionValidator()
        v.validate(make_txn(amount=1.0))  # no exception

    def test_zero_amount_fails(self):
        v = TransactionValidator()
        with pytest.raises(ValidationError, match="greater than 0"):
            v.validate(make_txn(amount=0.0))

    def test_negative_amount_fails(self):
        v = TransactionValidator()
        with pytest.raises(ValidationError, match="greater than 0"):
            v.validate(make_txn(amount=-10.0))

    def test_max_amount_passes(self):
        v = TransactionValidator()
        v.validate(make_txn(amount=50000.0))

    def test_over_max_amount_fails(self):
        v = TransactionValidator()
        with pytest.raises(ValidationError, match="exceeds the maximum"):
            v.validate(make_txn(amount=50000.01))


class TestCardTypeValidation:
    @pytest.mark.parametrize("card_type", [CardType.VISA, CardType.MC, CardType.AMEX, CardType.DISCOVER])
    def test_supported_card_types_pass(self, card_type):
        v = TransactionValidator()
        v.validate(make_txn(card_type=card_type))

    def test_unsupported_card_type_fails(self):
        """Validator rejects unknown card type strings."""
        v = TransactionValidator()
        # Bypass enum by patching card_type directly
        txn = make_txn()
        txn.card_type = "UNIONPAY"  # type: ignore[assignment]
        with pytest.raises(ValidationError, match="Unsupported card type"):
            v.validate(txn)


class TestCurrencyValidation:
    @pytest.mark.parametrize("currency", ["USD", "EUR", "GBP", "CAD"])
    def test_supported_currencies_pass(self, currency):
        v = TransactionValidator()
        v.validate(make_txn(currency=currency))

    def test_unsupported_currency_fails(self):
        v = TransactionValidator()
        with pytest.raises(ValidationError, match="Unsupported currency"):
            v.validate(make_txn(currency="JPY"))


class TestTerminalAndMerchantValidation:
    def test_empty_terminal_id_fails(self):
        v = TransactionValidator()
        with pytest.raises(ValidationError, match="terminal_id"):
            v.validate(make_txn(terminal_id=""))

    def test_whitespace_terminal_id_fails(self):
        v = TransactionValidator()
        with pytest.raises(ValidationError, match="terminal_id"):
            v.validate(make_txn(terminal_id="   "))

    def test_empty_merchant_id_fails(self):
        v = TransactionValidator()
        with pytest.raises(ValidationError, match="merchant_id"):
            v.validate(make_txn(merchant_id=""))


class TestDuplicateDetection:
    def test_duplicate_transaction_id_fails(self):
        txn = make_txn()
        v = TransactionValidator(seen_transaction_ids={txn.transaction_id})
        with pytest.raises(ValidationError, match="Duplicate transaction_id"):
            v.validate(txn)

    def test_fresh_transaction_id_passes(self):
        v = TransactionValidator(seen_transaction_ids={"other-id"})
        v.validate(make_txn())

    def test_register_seen_prevents_replay(self):
        txn = make_txn()
        v = TransactionValidator()
        v.validate(txn)
        v.register_seen(txn.transaction_id)
        with pytest.raises(ValidationError, match="Duplicate"):
            v.validate(txn)
