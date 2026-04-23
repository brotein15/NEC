"""
Network Execution Controller — central orchestrator.

The :class:`NetworkExecutionController` is the single entry point for all
POS transaction processing.  It wires together validation, security,
routing, processing, and ledger persistence in a thread-safe pipeline.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict

from config.settings import get_settings
from core.processor import PaymentProcessor, ProcessingResult
from core.security import build_card_payload, encrypt_payload, hash_payload
from core.transaction import Transaction, TransactionStatus
from core.validator import TransactionValidator, ValidationError
from network.gateway import GatewayTimeoutError
from network.router import TransactionRouter
from storage.ledger import TransactionLedger

logger = logging.getLogger(__name__)

settings = get_settings()


class NetworkExecutionController:
    """
    Central orchestrator for POS payment transaction processing.

    Processing pipeline (per transaction)
    --------------------------------------
    1. **Validate** — Apply business-rule and fraud checks.
    2. **Encrypt** — Protect sensitive card data with Fernet encryption.
    3. **Route** — Select the appropriate payment gateway via the router.
    4. **Process** — Apply processor rules (blocked cards, thresholds, fees).
    5. **Log** — Persist the finalised transaction in the in-memory ledger.
    6. **Respond** — Return a sanitised dict with no raw card data.

    The controller is thread-safe: a single :class:`threading.Lock` serialises
    writes to shared state (the validator's seen-ID set and the ledger).

    Retry logic
    -----------
    Gateway timeouts trigger up to ``MAX_RETRIES`` retries with a brief
    back-off.  If all retries are exhausted the transaction is marked FAILED.
    """

    def __init__(self) -> None:
        self._ledger = TransactionLedger()
        self._router = TransactionRouter()
        self._processor = PaymentProcessor()
        self._validator = TransactionValidator()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def submit(self, txn: Transaction) -> Dict:
        """
        Submit a :class:`~core.transaction.Transaction` for processing.

        Parameters
        ----------
        txn:
            Transaction to process.  The object is mutated in-place to
            reflect the final status and auth code.

        Returns
        -------
        dict
            A sanitised response dictionary (see
            :meth:`~core.transaction.Transaction.to_safe_dict`).  Never
            contains raw card data or the encrypted payload.

        Notes
        -----
        If the transaction has already been seen (duplicate ID), a
        :class:`~core.validator.ValidationError` is raised and the
        transaction is not processed.
        """
        logger.info(
            "NEC received transaction %s | terminal=%s | merchant=%s | "
            "amount=%.2f %s | card_type=%s | last4=%s",
            txn.transaction_id,
            txn.terminal_id,
            txn.merchant_id,
            txn.amount,
            txn.currency,
            txn.card_type,
            txn.card_last4,
        )

        # ---- 1. Validate ------------------------------------------------ #
        with self._lock:
            # Refresh seen IDs from the ledger (handles multi-instance scenarios)
            self._validator._seen = self._ledger.get_seen_ids()
            try:
                self._validator.validate(txn)
            except ValidationError as exc:
                logger.warning("Transaction %s failed validation: %s", txn.transaction_id, exc)
                txn.status = TransactionStatus.FAILED
                self._ledger.record(txn)
                return {**txn.to_safe_dict(), "error": str(exc)}

        # ---- 2. Encrypt sensitive data ----------------------------------- #
        payload_str = build_card_payload(txn.card_last4, str(txn.card_type), txn.terminal_id)
        txn.encrypted_payload = encrypt_payload(payload_str)
        payload_hash = hash_payload(payload_str)
        logger.debug("Payload hash for %s: %s", txn.transaction_id, payload_hash)

        # ---- 3 & 4. Route to gateway + process (with retry) -------------- #
        result = self._process_with_retry(txn)

        # ---- 5. Update transaction and commit to ledger ------------------ #
        txn.status = result.status
        txn.auth_code = result.auth_code

        with self._lock:
            self._ledger.record(txn)

        logger.info(
            "Transaction %s finalised | status=%s | auth_code=%s | fee=%.2f",
            txn.transaction_id,
            txn.status,
            txn.auth_code,
            result.fee,
        )

        # ---- 6. Return sanitised response -------------------------------- #
        response = txn.to_safe_dict()
        response["processing_fee"] = result.fee
        response["message"] = result.message
        return response

    def get_transaction(self, transaction_id: str):
        """
        Retrieve a previously processed transaction from the ledger.

        Parameters
        ----------
        transaction_id:
            UUID string of the target transaction.

        Returns
        -------
        Transaction or None
        """
        return self._ledger.get(transaction_id)

    def list_transactions(
        self,
        terminal_id: str | None = None,
        merchant_id: str | None = None,
    ):
        """
        Return transactions, optionally filtered by terminal or merchant.

        Parameters
        ----------
        terminal_id:
            If provided, return only transactions from this terminal.
        merchant_id:
            If provided, return only transactions for this merchant.

        Returns
        -------
        list of Transaction
        """
        if terminal_id:
            return self._ledger.get_by_terminal(terminal_id)
        if merchant_id:
            return self._ledger.get_by_merchant(merchant_id)
        return self._ledger.all()

    def get_stats(self) -> dict:
        """
        Return aggregate ledger statistics.

        Returns
        -------
        dict
            See :meth:`~storage.ledger.TransactionLedger.get_summary_stats`.
        """
        return self._ledger.get_summary_stats()

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _process_with_retry(self, txn: Transaction) -> ProcessingResult:
        """
        Attempt gateway routing and processing, retrying on timeout.

        Parameters
        ----------
        txn:
            The transaction to process.

        Returns
        -------
        ProcessingResult
            The result from the processor (may be FAILED after all retries
            are exhausted).
        """
        last_error: Exception | None = None
        for attempt in range(1, settings.MAX_RETRIES + 1):
            try:
                # Route to gateway (may raise GatewayTimeoutError)
                self._router.route(txn)
                # Process the transaction
                return self._processor.process(txn)
            except GatewayTimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Transaction %s gateway timeout on attempt %d/%d: %s",
                    txn.transaction_id,
                    attempt,
                    settings.MAX_RETRIES,
                    exc,
                )
                if attempt < settings.MAX_RETRIES:
                    time.sleep(0.2 * attempt)  # simple exponential back-off

        logger.error(
            "Transaction %s failed after %d retries: %s",
            txn.transaction_id,
            settings.MAX_RETRIES,
            last_error,
        )
        return ProcessingResult(
            status=TransactionStatus.FAILED,
            auth_code="",
            message=f"Transaction failed after {settings.MAX_RETRIES} retries due to gateway timeout.",
            fee=0.0,
        )
