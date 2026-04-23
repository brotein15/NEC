"""
NEC CLI entry point.

Usage
-----
Start the REST API server::

    python main.py serve

Run a demo simulation with 10 sample POS transactions::

    python main.py demo
"""

from __future__ import annotations

import logging
import random
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger("nec.main")


def cmd_serve() -> None:
    """Start the FastAPI server using uvicorn."""
    import uvicorn

    from config.settings import get_settings

    settings = get_settings()
    logger.info(
        "Starting NEC API server on %s:%d …", settings.API_HOST, settings.API_PORT
    )
    uvicorn.run(
        "api.server:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=False,
        log_level="info",
    )


def cmd_demo() -> None:
    """Send 10 sample POS transactions through the NEC pipeline and print results."""
    from core.controller import NetworkExecutionController
    from core.transaction import CardType, Transaction

    controller = NetworkExecutionController()

    sample_transactions = [
        # Regular approved transactions
        {"terminal_id": "TERM-001", "merchant_id": "MERCH-A", "card_last4": "1234", "card_type": CardType.VISA,     "amount": 49.99,   "currency": "USD"},
        {"terminal_id": "TERM-002", "merchant_id": "MERCH-B", "card_last4": "5678", "card_type": CardType.MC,       "amount": 120.00,  "currency": "EUR"},
        {"terminal_id": "TERM-003", "merchant_id": "MERCH-A", "card_last4": "9012", "card_type": CardType.AMEX,     "amount": 850.00,  "currency": "USD"},
        {"terminal_id": "TERM-001", "merchant_id": "MERCH-C", "card_last4": "3456", "card_type": CardType.DISCOVER, "amount": 22.50,   "currency": "GBP"},
        # Blocked card
        {"terminal_id": "TERM-004", "merchant_id": "MERCH-D", "card_last4": "0000", "card_type": CardType.VISA,     "amount": 75.00,   "currency": "USD"},
        # Manual review threshold
        {"terminal_id": "TERM-005", "merchant_id": "MERCH-E", "card_last4": "1111", "card_type": CardType.MC,       "amount": 15000.00,"currency": "USD"},
        # More normal transactions
        {"terminal_id": "TERM-002", "merchant_id": "MERCH-B", "card_last4": "2222", "card_type": CardType.VISA,     "amount": 9.99,    "currency": "CAD"},
        {"terminal_id": "TERM-006", "merchant_id": "MERCH-F", "card_last4": "3333", "card_type": CardType.AMEX,     "amount": 4500.00, "currency": "USD"},
        {"terminal_id": "TERM-007", "merchant_id": "MERCH-A", "card_last4": "4444", "card_type": CardType.DISCOVER, "amount": 299.00,  "currency": "USD"},
        {"terminal_id": "TERM-008", "merchant_id": "MERCH-G", "card_last4": "5555", "card_type": CardType.MC,       "amount": 1200.00, "currency": "EUR"},
    ]

    print("\n" + "=" * 60)
    print("  Network Execution Controller — Demo Simulation")
    print("=" * 60)

    for i, params in enumerate(sample_transactions, 1):
        txn = Transaction(**params)
        print(f"\n[{i:02d}] Submitting txn {txn.transaction_id[:8]}… ", end="", flush=True)
        result = controller.submit(txn)
        status_icon = {"APPROVED": "✅", "DECLINED": "❌", "FAILED": "💥"}.get(result["status"], "?")
        print(
            f"{status_icon} {result['status']}"
            + (f" | auth={result['auth_code']}" if result.get("auth_code") else "")
            + (f" | fee=${result.get('processing_fee', 0):.2f}" if result.get("processing_fee") else "")
        )
        print(f"     → {result.get('message', '')}")

    print("\n" + "-" * 60)
    stats = controller.get_stats()
    print("Ledger Summary Stats")
    print(f"  Total transactions : {stats['total_transactions']}")
    print(f"  Total volume       : ${stats['total_volume']:,.2f}")
    print(f"  Approved           : {stats['approved_count']}")
    print(f"  Declined           : {stats['declined_count']}")
    print(f"  Failed             : {stats['failed_count']}")
    print(f"  Approval rate      : {stats['approval_rate']:.1%}")
    print(f"  Average amount     : ${stats['average_amount']:,.2f}")
    print("=" * 60 + "\n")


def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate command."""
    commands = {"serve": cmd_serve, "demo": cmd_demo}

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: python main.py [{' | '.join(commands)}]")
        sys.exit(1)

    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
