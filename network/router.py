"""
Transaction router for the Network Execution Controller.

Routes each transaction to the appropriate :class:`~network.gateway.PaymentGateway`
based on card type.  AMEX cards are directed to a premium gateway; all other
supported card types use the standard gateway.
"""

from __future__ import annotations

import logging

from core.transaction import CardType, Transaction
from network.gateway import GatewayResponse, PaymentGateway

logger = logging.getLogger(__name__)

# Module-level gateway singletons (created once, reused across requests).
_STANDARD_GATEWAY = PaymentGateway(name="StandardGateway")
_PREMIUM_GATEWAY = PaymentGateway(name="PremiumGateway")


class TransactionRouter:
    """
    Routes transactions to the correct payment gateway based on card type.

    Routing rules
    -------------
    - **AMEX** → ``PremiumGateway`` (higher limits, direct network access).
    - **VISA / MC / DISCOVER** → ``StandardGateway``.
    """

    def route(self, txn: Transaction) -> GatewayResponse:
        """
        Determine the appropriate gateway for *txn* and submit it.

        Parameters
        ----------
        txn:
            A validated transaction ready for network submission.

        Returns
        -------
        GatewayResponse
            The gateway's response to the submission.

        Raises
        ------
        ~network.gateway.GatewayTimeoutError
            Propagated from the selected gateway if a simulated timeout occurs.
        """
        gateway = self._select_gateway(txn.card_type)
        logger.info(
            "Routing transaction %s (card_type=%s) to %s.",
            txn.transaction_id,
            txn.card_type,
            gateway.name,
        )
        return gateway.send(txn.transaction_id, txn.amount)

    @staticmethod
    def _select_gateway(card_type) -> PaymentGateway:
        """
        Select the gateway for the given *card_type*.

        Parameters
        ----------
        card_type:
            A :class:`~core.transaction.CardType` value or equivalent string.

        Returns
        -------
        PaymentGateway
            The chosen gateway instance.
        """
        value = card_type.value if hasattr(card_type, "value") else card_type
        if value == CardType.AMEX.value:
            return _PREMIUM_GATEWAY
        return _STANDARD_GATEWAY
