"""
Security utilities for the Network Execution Controller.

Provides:
- Fernet symmetric encryption for sensitive card data.
- SHA-256 payload hashing for integrity verification.
- HMAC-SHA256 signed token generation and validation.
- Card number masking helpers.
- Auth-code generation and verification.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken

from config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


# --------------------------------------------------------------------------- #
# Encryption
# --------------------------------------------------------------------------- #

def _get_fernet() -> Fernet:
    """
    Return a Fernet instance initialised with the configured key.

    The key is expected to be a URL-safe base-64 encoded 32-byte value.
    If the configured key is not a valid Fernet key a new one is generated
    and a warning is emitted (development fallback only).
    """
    key = settings.FERNET_KEY.encode()
    try:
        return Fernet(key)
    except Exception:
        logger.warning(
            "Invalid Fernet key in config — generating an ephemeral key. "
            "Set NEC_FERNET_KEY to a valid Fernet key in production."
        )
        return Fernet(Fernet.generate_key())


_fernet = _get_fernet()


def encrypt_payload(data: str) -> str:
    """
    Encrypt *data* using Fernet symmetric encryption.

    Parameters
    ----------
    data:
        Plain-text string to encrypt (e.g. JSON-serialised card data).

    Returns
    -------
    str
        URL-safe base-64 encoded cipher-text.
    """
    token = _fernet.encrypt(data.encode())
    return token.decode()


def decrypt_payload(token: str) -> str:
    """
    Decrypt a Fernet-encrypted *token*.

    Parameters
    ----------
    token:
        Cipher-text produced by :func:`encrypt_payload`.

    Returns
    -------
    str
        Original plain-text string.

    Raises
    ------
    ValueError
        If *token* is invalid or has been tampered with.
    """
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Invalid or tampered encrypted payload.") from exc


# --------------------------------------------------------------------------- #
# Hashing
# --------------------------------------------------------------------------- #

def hash_payload(data: str) -> str:
    """
    Compute a SHA-256 hex digest of *data*.

    Used for transaction integrity checks — store the hash alongside the
    transaction and recompute on retrieval to detect tampering.

    Parameters
    ----------
    data:
        String to hash (typically a canonical JSON representation of the
        transaction fields).

    Returns
    -------
    str
        Lowercase hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(data.encode()).hexdigest()


# --------------------------------------------------------------------------- #
# HMAC token auth
# --------------------------------------------------------------------------- #

def generate_api_token(payload: str) -> str:
    """
    Generate an HMAC-SHA256 signed token for *payload*.

    The token format is ``<payload>.<hex-signature>``.

    Parameters
    ----------
    payload:
        Arbitrary string to sign (e.g. a client ID or timestamp).

    Returns
    -------
    str
        Signed token string.
    """
    sig = hmac.new(
        settings.API_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{sig}"


def validate_api_token(token: str) -> bool:
    """
    Validate an HMAC-SHA256 signed *token*.

    Parameters
    ----------
    token:
        Token string previously produced by :func:`generate_api_token`.

    Returns
    -------
    bool
        ``True`` if the signature is valid, ``False`` otherwise.
    """
    try:
        payload, signature = token.rsplit(".", 1)
    except ValueError:
        return False

    expected = hmac.new(
        settings.API_SECRET_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def validate_api_key(api_key: str) -> bool:
    """
    Validate a plain API key against the configured secret.

    Uses a constant-time comparison to prevent timing attacks.

    Parameters
    ----------
    api_key:
        Key supplied by the caller (e.g. from the ``X-API-Key`` header).

    Returns
    -------
    bool
        ``True`` if *api_key* matches the configured key.
    """
    return hmac.compare_digest(
        api_key.encode(),
        settings.API_KEY.encode(),
    )


# --------------------------------------------------------------------------- #
# Card masking
# --------------------------------------------------------------------------- #

def mask_card(card_number: str) -> str:
    """
    Mask all but the last four digits of *card_number*.

    Parameters
    ----------
    card_number:
        Full card PAN or any string whose tail should be preserved.

    Returns
    -------
    str
        Masked string, e.g. ``"****-****-****-1234"``.
    """
    last4 = card_number[-4:] if len(card_number) >= 4 else card_number
    return f"****-****-****-{last4}"


# --------------------------------------------------------------------------- #
# Auth codes
# --------------------------------------------------------------------------- #

def generate_auth_code() -> str:
    """
    Generate a random 6-character upper-case alphanumeric auth code.

    Returns
    -------
    str
        Auth code, e.g. ``"A3X9QZ"``.
    """
    return secrets.token_hex(3).upper()


def build_card_payload(card_last4: str, card_type: str, terminal_id: str) -> str:
    """
    Build a canonical string representation of sensitive card data for encryption.

    Parameters
    ----------
    card_last4:
        Last four digits of the payment card.
    card_type:
        Card network identifier.
    terminal_id:
        Originating terminal identifier.

    Returns
    -------
    str
        Pipe-delimited payload string.
    """
    return f"card_last4={card_last4}|card_type={card_type}|terminal_id={terminal_id}"
