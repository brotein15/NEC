"""
Application configuration loaded from environment variables.

All sensitive values have safe defaults suitable for local development.
In production, override every value via real environment variables or a .env file.
"""

import os
import secrets
from functools import lru_cache


class Settings:
    """Centralised configuration object for the NEC application."""

    # ------------------------------------------------------------------ #
    # API security
    # ------------------------------------------------------------------ #
    #: Secret used to sign/verify HMAC-SHA256 API tokens.
    API_SECRET_KEY: str = os.getenv(
        "NEC_API_SECRET_KEY",
        "dev-secret-key-change-in-production-32chars!",
    )

    #: Pre-shared API key accepted by the REST API (X-API-Key header).
    API_KEY: str = os.getenv(
        "NEC_API_KEY",
        "dev-api-key-change-in-production",
    )

    # ------------------------------------------------------------------ #
    # Encryption
    # ------------------------------------------------------------------ #
    #: Fernet key (URL-safe base-64 encoded 32-byte key).
    #: Generate with: from cryptography.fernet import Fernet; Fernet.generate_key()
    FERNET_KEY: str = os.getenv(
        "NEC_FERNET_KEY",
        "dGhpcy1pcy1hLTMyLWJ5dGUtZmVybmV0LWtleS0hISE=",
    )

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    API_HOST: str = os.getenv("NEC_API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("NEC_API_PORT", "8000"))

    # ------------------------------------------------------------------ #
    # Processing limits
    # ------------------------------------------------------------------ #
    MAX_TRANSACTION_AMOUNT: float = float(
        os.getenv("NEC_MAX_TRANSACTION_AMOUNT", "50000.0")
    )
    #: Transactions above this threshold are auto-declined pending manual review.
    MANUAL_REVIEW_THRESHOLD: float = float(
        os.getenv("NEC_MANUAL_REVIEW_THRESHOLD", "10000.0")
    )

    PROCESSING_FEE_PERCENT: float = 0.029   # 2.9 %
    PROCESSING_FEE_FLAT: float = 0.30       # $0.30

    # ------------------------------------------------------------------ #
    # Supported values
    # ------------------------------------------------------------------ #
    SUPPORTED_CURRENCIES: tuple = ("USD", "EUR", "GBP", "CAD")
    SUPPORTED_CARD_TYPES: tuple = ("VISA", "MC", "AMEX", "DISCOVER")

    # ------------------------------------------------------------------ #
    # Gateway simulation
    # ------------------------------------------------------------------ #
    GATEWAY_TIMEOUT_CHANCE: float = 0.05   # 5 % simulated timeout rate
    GATEWAY_MIN_LATENCY: float = 0.1       # seconds
    GATEWAY_MAX_LATENCY: float = 0.5       # seconds

    # ------------------------------------------------------------------ #
    # Retry
    # ------------------------------------------------------------------ #
    MAX_RETRIES: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
