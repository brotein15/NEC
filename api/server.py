"""
FastAPI REST API for the Network Execution Controller.

Exposes a POS-facing HTTP interface for submitting and querying payment
transactions, with HMAC-backed API key authentication.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

from core.controller import NetworkExecutionController
from core.security import validate_api_key
from core.transaction import CardType, Transaction, TransactionStatus

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# FastAPI app & shared controller instance
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="Network Execution Controller (NEC)",
    description="Secure POS payment transaction processing API.",
    version="1.0.0",
)

_controller = NetworkExecutionController()

# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: Optional[str] = Depends(_api_key_header)) -> str:
    """
    FastAPI dependency that enforces API key authentication.

    Raises
    ------
    HTTPException (403)
        If the ``X-API-Key`` header is missing or invalid.
    """
    if not api_key or not validate_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )
    return api_key


# --------------------------------------------------------------------------- #
# Request / Response models
# --------------------------------------------------------------------------- #

class TransactionRequest(BaseModel):
    """Pydantic model for incoming POS transaction submissions."""

    terminal_id: str = Field(..., min_length=1, description="POS terminal identifier")
    merchant_id: str = Field(..., min_length=1, description="Merchant account identifier")
    card_last4: str = Field(..., min_length=4, max_length=4, description="Last 4 digits of the card")
    card_type: CardType = Field(..., description="Card network (VISA/MC/AMEX/DISCOVER)")
    amount: float = Field(..., gt=0, description="Transaction amount")
    currency: str = Field(..., description="ISO 4217 currency code")

    @field_validator("card_last4")
    @classmethod
    def card_last4_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("card_last4 must contain only digits.")
        return v

    @field_validator("currency")
    @classmethod
    def currency_must_be_supported(cls, v: str) -> str:
        from config.settings import get_settings
        settings = get_settings()
        if v not in settings.SUPPORTED_CURRENCIES:
            raise ValueError(
                f"Unsupported currency '{v}'. "
                f"Supported: {settings.SUPPORTED_CURRENCIES}"
            )
        return v


class TransactionResponse(BaseModel):
    """Pydantic model for outgoing transaction responses (no raw card data)."""

    transaction_id: str
    terminal_id: str
    merchant_id: str
    card_last4: str
    card_type: str
    amount: float
    currency: str
    timestamp: str
    status: str
    auth_code: str
    processing_fee: Optional[float] = None
    message: Optional[str] = None
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@app.get("/health", tags=["System"])
def health_check():
    """Health-check endpoint — no auth required."""
    return {"status": "ok", "service": "NEC"}


@app.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Transactions"],
    dependencies=[Depends(require_api_key)],
)
def submit_transaction(req: TransactionRequest):
    """
    Submit a new POS payment transaction for processing.

    Requires a valid ``X-API-Key`` header.
    """
    txn = Transaction(
        terminal_id=req.terminal_id,
        merchant_id=req.merchant_id,
        card_last4=req.card_last4,
        card_type=req.card_type,
        amount=req.amount,
        currency=req.currency,
    )
    result = _controller.submit(txn)
    return TransactionResponse(**result)


@app.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
    tags=["Transactions"],
    dependencies=[Depends(require_api_key)],
)
def get_transaction(transaction_id: str):
    """
    Retrieve the current status of a previously submitted transaction.

    Requires a valid ``X-API-Key`` header.
    """
    txn = _controller.get_transaction(transaction_id)
    if txn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transaction '{transaction_id}' not found.",
        )
    return TransactionResponse(**txn.to_safe_dict())


@app.get(
    "/transactions",
    response_model=List[TransactionResponse],
    tags=["Transactions"],
    dependencies=[Depends(require_api_key)],
)
def list_transactions(
    terminal_id: Optional[str] = Query(None, description="Filter by terminal ID"),
    merchant_id: Optional[str] = Query(None, description="Filter by merchant ID"),
):
    """
    List all transactions, optionally filtered by terminal or merchant.

    Requires a valid ``X-API-Key`` header.
    """
    txns = _controller.list_transactions(
        terminal_id=terminal_id, merchant_id=merchant_id
    )
    return [TransactionResponse(**t.to_safe_dict()) for t in txns]


@app.get("/stats", tags=["System"], dependencies=[Depends(require_api_key)])
def get_stats():
    """
    Return aggregate statistics from the in-memory ledger.

    Requires a valid ``X-API-Key`` header.
    """
    return _controller.get_stats()
