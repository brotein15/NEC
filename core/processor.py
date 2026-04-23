"""
Payment processing logic for the Network Execution Controller.

Simulates downstream gateway behaviour, applies business rules
(manual-review threshold, blocked-card detection), and calculates
processing fees.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

from config.settings import get_settings
from core.security import generate_auth_code
from core.transaction import Transaction, TransactionStatus

logger = logging.getLogger(__name__)

settings = get_settings()


@dataclass
class ProcessingResult:
    """
    Structured result returned by the payment processor.

    Attributes
    ----------
    status:
        Final :class:`~core.transaction.TransactionStatus` after processing.
    auth_code:
        Six-character authorisation code (non-empty only for approved txns).
    message:
        Human-readable description of the processing outcome.
    fee:
        Processing fee in the same currency as the transaction amount.
    """

    status: TransactionStatus
    auth_code: str
    message: str
    fee: float


class PaymentProcessor:
    """
    Simulates payment processing including gateway interaction, fraud rules,
    and fee calculation.

    Business rules applied in order
    --------------------------------
    1. Cards with last4 ``"0000"`` are unconditionally declined (test blocked card).
    2. Transactions above ``MANUAL_REVIEW_THRESHOLD`` are declined for manual review.
    3. All other transactions are approved or declined with a small random chance
       (``10 %`` random decline rate to simulate gateway responses).
    """

    # Probability that a valid transaction is randomly declined by the gateway.
    _RANDOM_DECLINE_RATE: float = 0.10

    def process(self, txn: Transaction) -> ProcessingResult:
        """
        Process a validated :class:`~core.transaction.Transaction`.

        Parameters
        ----------
        txn:
            The transaction to process.  Must have already passed validation.

        Returns
        -------
        ProcessingResult
            Structured result capturing the outcome, auth code, message, and fee.
        """
        fee = self._calculate_fee(txn.amount)
        logger.info(
            "Processing transaction %s | amount=%.2f | fee=%.2f",
            txn.transaction_id,
            txn.amount,
            fee,
        )

        # Rule 1 — blocked test card
        if txn.card_last4 == "0000":
            logger.warning(
                "Transaction %s declined: blocked card (last4=0000).",
                txn.transaction_id,
            )
            return ProcessingResult(
                status=TransactionStatus.DECLINED,
                auth_code="",
                message="Card declined: blocked test card.",
                fee=0.0,
            )

        # Rule 2 — manual review threshold
        if txn.amount > settings.MANUAL_REVIEW_THRESHOLD:
            logger.warning(
                "Transaction %s declined: amount %.2f exceeds manual-review threshold.",
                txn.transaction_id,
                txn.amount,
            )
            return ProcessingResult(
                status=TransactionStatus.DECLINED,
                auth_code="",
                message=(
                    f"Transaction amount ${txn.amount:.2f} exceeds the "
                    f"${settings.MANUAL_REVIEW_THRESHOLD:,.0f} automatic-approval "
                    "limit and requires manual review."
                ),
                fee=0.0,
            )

        # Rule 3 — random decline simulation
        if random.random() < self._RANDOM_DECLINE_RATE:
            logger.info(
                "Transaction %s randomly declined by gateway simulation.",
                txn.transaction_id,
            )
            return ProcessingResult(
                status=TransactionStatus.DECLINED,
                auth_code="",
                message="Transaction declined by payment network.",
                fee=0.0,
            )

        # All checks passed — approve
        auth_code = generate_auth_code()
        logger.info(
            "Transaction %s approved | auth_code=%s",
            txn.transaction_id,
            auth_code,
        )
        return ProcessingResult(
            status=TransactionStatus.APPROVED,
            auth_code=auth_code,
            message="Transaction approved.",
            fee=fee,
        )

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _calculate_fee(amount: float) -> float:
        """
        Compute the processing fee for *amount*.

        Fee formula: ``amount * 2.9% + $0.30``

        Parameters
        ----------
        amount:
            Transaction amount in the originating currency.

        Returns
        -------
        float
            Processing fee rounded to two decimal places.
        """
        fee = amount * settings.PROCESSING_FEE_PERCENT + settings.PROCESSING_FEE_FLAT
        return round(fee, 2)
