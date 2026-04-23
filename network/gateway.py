"""
Simulated payment gateway interface.

Models a real-world payment gateway with configurable network latency and an
occasional simulated timeout to exercise the retry logic in the controller.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

from config.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class GatewayTimeoutError(Exception):
    """Raised when the simulated gateway does not respond in time."""


@dataclass
class GatewayResponse:
    """
    Structured response from the payment gateway.

    Attributes
    ----------
    approved:
        Whether the gateway approved the transaction.
    approval_code:
        Alphanumeric code provided by the gateway on approval.
    response_code:
        ISO 8583-style response code (``"00"`` = approved, others = declined).
    message:
        Human-readable gateway message.
    """

    approved: bool
    approval_code: str
    response_code: str
    message: str


class PaymentGateway:
    """
    Simulated payment gateway that introduces realistic network latency and
    occasional timeouts.

    The gateway is intentionally simple: it always approves unless the caller
    triggers the timeout simulation.  Real decline logic lives in the
    :mod:`core.processor` layer.

    Parameters
    ----------
    name:
        Human-readable identifier for this gateway instance (used in logs).
    """

    def __init__(self, name: str = "StandardGateway") -> None:
        self.name = name

    def send(self, transaction_id: str, amount: float) -> GatewayResponse:
        """
        Submit a transaction to the (simulated) gateway and return its response.

        Simulates:
        - Random network latency between ``GATEWAY_MIN_LATENCY`` and
          ``GATEWAY_MAX_LATENCY`` seconds.
        - A ``GATEWAY_TIMEOUT_CHANCE`` probability of raising
          :class:`GatewayTimeoutError`.

        Parameters
        ----------
        transaction_id:
            The unique ID of the transaction being submitted.
        amount:
            Transaction amount (informational; logged only).

        Returns
        -------
        GatewayResponse
            Gateway approval response.

        Raises
        ------
        GatewayTimeoutError
            With ``GATEWAY_TIMEOUT_CHANCE`` probability.
        """
        latency = random.uniform(
            settings.GATEWAY_MIN_LATENCY, settings.GATEWAY_MAX_LATENCY
        )
        logger.debug(
            "[%s] Simulating %.3fs network latency for txn %s.",
            self.name,
            latency,
            transaction_id,
        )
        time.sleep(latency)

        if random.random() < settings.GATEWAY_TIMEOUT_CHANCE:
            logger.warning(
                "[%s] Simulated timeout for transaction %s.",
                self.name,
                transaction_id,
            )
            raise GatewayTimeoutError(
                f"Gateway '{self.name}' timed out for transaction {transaction_id}."
            )

        return GatewayResponse(
            approved=True,
            approval_code=f"GW-{transaction_id[:8].upper()}",
            response_code="00",
            message=f"Approved by {self.name}",
        )
