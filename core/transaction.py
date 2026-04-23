"""
Transaction data model for the Network Execution Controller.

Defines the core ``Transaction`` dataclass and related enumerations used
throughout the NEC pipeline.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class TransactionStatus(str, Enum):
    """Lifecycle states a POS transaction may occupy."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    FAILED = "FAILED"


class CardType(str, Enum):
    """Supported payment card networks."""

    VISA = "VISA"
    MC = "MC"
    AMEX = "AMEX"
    DISCOVER = "DISCOVER"


@dataclass
class Transaction:
    """
    Represents a single POS payment transaction travelling through the NEC.

    Attributes
    ----------
    terminal_id:
        Unique identifier of the POS terminal that originated the transaction.
    merchant_id:
        Identifier of the merchant account associated with this transaction.
    card_last4:
        Last four digits of the payment card (never store full PAN).
    card_type:
        Payment network of the card (VISA, MC, AMEX, DISCOVER).
    amount:
        Transaction amount in the specified currency.
    currency:
        ISO 4217 currency code (USD, EUR, GBP, CAD).
    transaction_id:
        UUID4 string auto-generated at creation time.
    timestamp:
        UTC datetime auto-set at creation time.
    status:
        Current lifecycle status; starts as PENDING.
    auth_code:
        Authorization code assigned on approval; empty until then.
    encrypted_payload:
        Fernet-encrypted representation of sensitive card data; set during
        the security phase of processing.
    """

    terminal_id: str
    merchant_id: str
    card_last4: str
    card_type: CardType
    amount: float
    currency: str

    # Auto-generated fields
    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: TransactionStatus = field(default=TransactionStatus.PENDING)
    auth_code: str = field(default="")
    encrypted_payload: str = field(default="")

    def to_safe_dict(self) -> dict:
        """
        Return a dict representation safe for logging and API responses.

        Raw card numbers are never included.  ``encrypted_payload`` is
        omitted to avoid leaking cipher-text in public-facing responses.
        """
        return {
            "transaction_id": self.transaction_id,
            "terminal_id": self.terminal_id,
            "merchant_id": self.merchant_id,
            "card_last4": self.card_last4,
            "card_type": self.card_type.value if isinstance(self.card_type, CardType) else self.card_type,
            "amount": self.amount,
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value if isinstance(self.status, TransactionStatus) else self.status,
            "auth_code": self.auth_code,
        }
