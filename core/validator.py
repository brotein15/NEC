"""
Transaction validation rules for the Network Execution Controller.

All validation logic is collected here so that rules can be tested in
isolation and swapped out without touching the processing pipeline.
"""

from __future__ import annotations

import logging
from typing import Optional

from config.settings import get_settings
from core.transaction import Transaction

logger = logging.getLogger(__name__)

settings = get_settings()


class ValidationError(Exception):
    """Raised when a transaction fails one or more validation rules."""


class TransactionValidator:
    """
    Stateless validator that applies a suite of business rules to a
    :class:`~core.transaction.Transaction` before it enters the processing
    pipeline.

    Parameters
    ----------
    seen_transaction_ids:
        Optional set of already-processed transaction IDs used for duplicate
        detection.  Typically supplied by the ledger.
    """

    def __init__(self, seen_transaction_ids: Optional[set] = None) -> None:
        self._seen: set = seen_transaction_ids or set()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def validate(self, txn: Transaction) -> None:
        """
        Run all validation rules against *txn*.

        Raises
        ------
        ValidationError
            On the first rule that is violated, with a human-readable message.
        """
        self._validate_amount(txn.amount)
        self._validate_card_type(txn.card_type)
        self._validate_currency(txn.currency)
        self._validate_terminal_id(txn.terminal_id)
        self._validate_merchant_id(txn.merchant_id)
        self._validate_duplicate(txn.transaction_id)
        logger.debug("Transaction %s passed all validation rules.", txn.transaction_id)

    # ------------------------------------------------------------------ #
    # Individual rules
    # ------------------------------------------------------------------ #

    @staticmethod
    def _validate_amount(amount: float) -> None:
        """
        Ensure the transaction amount is positive and within the allowed
        per-transaction ceiling.

        Raises
        ------
        ValidationError
            If *amount* is ≤ 0 or exceeds the maximum threshold.
        """
        if amount <= 0:
            raise ValidationError(
                f"Transaction amount must be greater than 0; got {amount}."
            )
        if amount > settings.MAX_TRANSACTION_AMOUNT:
            raise ValidationError(
                f"Transaction amount {amount} exceeds the maximum allowed "
                f"amount of {settings.MAX_TRANSACTION_AMOUNT}."
            )

    @staticmethod
    def _validate_card_type(card_type) -> None:
        """
        Verify the card network is supported.

        Raises
        ------
        ValidationError
            If *card_type* is not in the configured set of supported types.
        """
        value = card_type.value if hasattr(card_type, "value") else card_type
        if value not in settings.SUPPORTED_CARD_TYPES:
            raise ValidationError(
                f"Unsupported card type '{value}'. "
                f"Supported types: {settings.SUPPORTED_CARD_TYPES}."
            )

    @staticmethod
    def _validate_currency(currency: str) -> None:
        """
        Verify the currency code is in the list of supported currencies.

        Raises
        ------
        ValidationError
            If *currency* is not supported.
        """
        if currency not in settings.SUPPORTED_CURRENCIES:
            raise ValidationError(
                f"Unsupported currency '{currency}'. "
                f"Supported currencies: {settings.SUPPORTED_CURRENCIES}."
            )

    @staticmethod
    def _validate_terminal_id(terminal_id: str) -> None:
        """
        Ensure *terminal_id* is a non-empty string.

        Raises
        ------
        ValidationError
            If *terminal_id* is blank.
        """
        if not terminal_id or not terminal_id.strip():
            raise ValidationError("terminal_id must be a non-empty string.")

    @staticmethod
    def _validate_merchant_id(merchant_id: str) -> None:
        """
        Ensure *merchant_id* is a non-empty string.

        Raises
        ------
        ValidationError
            If *merchant_id* is blank.
        """
        if not merchant_id or not merchant_id.strip():
            raise ValidationError("merchant_id must be a non-empty string.")

    def _validate_duplicate(self, transaction_id: str) -> None:
        """
        Check that *transaction_id* has not been processed before.

        Raises
        ------
        ValidationError
            If *transaction_id* is already in the seen-IDs set (potential
            replay / fraud).
        """
        if transaction_id in self._seen:
            raise ValidationError(
                f"Duplicate transaction_id detected: '{transaction_id}'. "
                "This may indicate a replay attack."
            )

    def register_seen(self, transaction_id: str) -> None:
        """
        Record *transaction_id* as having been processed.

        Should be called after a transaction is successfully committed to the
        ledger so that subsequent submissions of the same ID are rejected.

        Parameters
        ----------
        transaction_id:
            The UUID string of the processed transaction.
        """
        self._seen.add(transaction_id)
