"""
In-memory transaction ledger for the Network Execution Controller.

Stores all processed transactions in a thread-safe dictionary keyed by
``transaction_id`` and exposes query/summary helpers.
"""

from __future__ import annotations

import logging
import threading
from typing import Dict, List, Optional

from core.transaction import Transaction, TransactionStatus

logger = logging.getLogger(__name__)


class TransactionLedger:
    """
    Thread-safe, in-memory store for processed :class:`~core.transaction.Transaction`
    objects.

    All mutating operations acquire an internal :class:`threading.Lock` so the
    ledger is safe for concurrent use by multiple POS terminals.
    """

    def __init__(self) -> None:
        self._store: Dict[str, Transaction] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Write operations
    # ------------------------------------------------------------------ #

    def record(self, txn: Transaction) -> None:
        """
        Persist *txn* in the ledger.

        If a transaction with the same ``transaction_id`` already exists it is
        overwritten (idempotent upsert semantics).

        Parameters
        ----------
        txn:
            The transaction to store.
        """
        with self._lock:
            self._store[txn.transaction_id] = txn
            logger.debug("Ledger recorded transaction %s.", txn.transaction_id)

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #

    def get(self, transaction_id: str) -> Optional[Transaction]:
        """
        Retrieve a single transaction by its ID.

        Parameters
        ----------
        transaction_id:
            UUID string of the target transaction.

        Returns
        -------
        Transaction or None
            The matching transaction, or ``None`` if not found.
        """
        return self._store.get(transaction_id)

    def get_by_terminal(self, terminal_id: str) -> List[Transaction]:
        """
        Return all transactions originating from *terminal_id*.

        Parameters
        ----------
        terminal_id:
            The POS terminal identifier to filter by.

        Returns
        -------
        list of Transaction
            Possibly empty list of matching transactions.
        """
        return [t for t in self._store.values() if t.terminal_id == terminal_id]

    def get_by_merchant(self, merchant_id: str) -> List[Transaction]:
        """
        Return all transactions associated with *merchant_id*.

        Parameters
        ----------
        merchant_id:
            The merchant account identifier to filter by.

        Returns
        -------
        list of Transaction
            Possibly empty list of matching transactions.
        """
        return [t for t in self._store.values() if t.merchant_id == merchant_id]

    def all(self) -> List[Transaction]:
        """
        Return a snapshot of all transactions in the ledger.

        Returns
        -------
        list of Transaction
        """
        return list(self._store.values())

    def get_seen_ids(self) -> set:
        """
        Return the set of all recorded transaction IDs.

        Used by the validator for duplicate detection.

        Returns
        -------
        set of str
        """
        return set(self._store.keys())

    # ------------------------------------------------------------------ #
    # Summary statistics
    # ------------------------------------------------------------------ #

    def get_summary_stats(self) -> dict:
        """
        Compute aggregate statistics over all recorded transactions.

        Returns
        -------
        dict
            Dictionary with the following keys:

            ``total_transactions``
                Total number of transactions in the ledger.
            ``total_volume``
                Sum of amounts for all transactions (regardless of status).
            ``approved_count``
                Number of transactions with status ``APPROVED``.
            ``declined_count``
                Number of transactions with status ``DECLINED``.
            ``failed_count``
                Number of transactions with status ``FAILED``.
            ``approval_rate``
                Fraction of transactions that were approved (0–1).
            ``average_amount``
                Mean transaction amount, or 0 if the ledger is empty.
        """
        transactions = list(self._store.values())
        total = len(transactions)
        if total == 0:
            return {
                "total_transactions": 0,
                "total_volume": 0.0,
                "approved_count": 0,
                "declined_count": 0,
                "failed_count": 0,
                "approval_rate": 0.0,
                "average_amount": 0.0,
            }

        approved = sum(
            1 for t in transactions if t.status == TransactionStatus.APPROVED
        )
        declined = sum(
            1 for t in transactions if t.status == TransactionStatus.DECLINED
        )
        failed = sum(
            1 for t in transactions if t.status == TransactionStatus.FAILED
        )
        total_volume = sum(t.amount for t in transactions)

        return {
            "total_transactions": total,
            "total_volume": round(total_volume, 2),
            "approved_count": approved,
            "declined_count": declined,
            "failed_count": failed,
            "approval_rate": round(approved / total, 4),
            "average_amount": round(total_volume / total, 2),
        }
