# NEC — Network Execution Controller

Securely processes POS (Point of Sale) payment transactions through a fully-typed Python pipeline featuring Fernet encryption, HMAC authentication, simulated gateway routing, an in-memory ledger, and a FastAPI REST interface.

---

## Architecture Overview

```
main.py                  ← CLI entry point (serve | demo)
config/settings.py       ← Env-based configuration (all secrets via env vars)
core/
  transaction.py         ← Transaction dataclass + CardType / TransactionStatus enums
  security.py            ← Fernet encryption · SHA-256 hashing · HMAC tokens · masking
  validator.py           ← Business-rule validation (amount, card type, currency, duplicates)
  processor.py           ← Gateway simulation, decline rules, fee calculation
  controller.py          ← NetworkExecutionController — orchestrates the full pipeline
network/
  gateway.py             ← Simulated payment gateway (latency + 5 % timeout simulation)
  router.py              ← Routes AMEX → PremiumGateway, others → StandardGateway
storage/
  ledger.py              ← Thread-safe in-memory transaction ledger + stats
api/
  server.py              ← FastAPI REST API with HMAC API-key auth
tests/                   ← pytest test suite
```

### Processing Pipeline

```
POS Terminal
    │
    ▼
NetworkExecutionController.submit()
    ├── 1. Validate     (TransactionValidator)
    ├── 2. Encrypt      (Fernet – core/security.py)
    ├── 3. Route        (TransactionRouter → PaymentGateway)
    ├── 4. Process      (PaymentProcessor – rules + fee)
    ├── 5. Log          (TransactionLedger)
    └── 6. Respond      (sanitised dict — no raw card data)
```

---

## Setup

### Prerequisites
- Python 3.10+

### Install

```bash
git clone https://github.com/brotein15/NEC.git
cd NEC
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Environment Variables (optional — safe defaults used for development)

| Variable | Description | Default |
|---|---|---|
| `NEC_API_SECRET_KEY` | HMAC signing secret | `dev-secret-key-...` |
| `NEC_API_KEY` | Pre-shared API key for `X-API-Key` header | `dev-api-key-...` |
| `NEC_FERNET_KEY` | Fernet symmetric encryption key | built-in dev key |
| `NEC_API_HOST` | Server bind host | `0.0.0.0` |
| `NEC_API_PORT` | Server port | `8000` |

---

## Running

### Start the API server

```bash
python main.py serve
```

### Run the demo simulation (10 sample transactions)

```bash
python main.py demo
```

---

## Example API Calls (`curl`)

> Replace `dev-api-key-change-in-production` with your `NEC_API_KEY` value.

### Health check (no auth required)

```bash
curl http://localhost:8000/health
```

### Submit a transaction

```bash
curl -X POST http://localhost:8000/transactions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key-change-in-production" \
  -d '{
    "terminal_id": "TERM-001",
    "merchant_id": "MERCH-A",
    "card_last4": "1234",
    "card_type": "VISA",
    "amount": 49.99,
    "currency": "USD"
  }'
```

### Get a transaction by ID

```bash
curl http://localhost:8000/transactions/<transaction_id> \
  -H "X-API-Key: dev-api-key-change-in-production"
```

### List all transactions

```bash
curl "http://localhost:8000/transactions" \
  -H "X-API-Key: dev-api-key-change-in-production"
```

### Filter by terminal or merchant

```bash
curl "http://localhost:8000/transactions?terminal_id=TERM-001" \
  -H "X-API-Key: dev-api-key-change-in-production"

curl "http://localhost:8000/transactions?merchant_id=MERCH-A" \
  -H "X-API-Key: dev-api-key-change-in-production"
```

### Ledger statistics

```bash
curl http://localhost:8000/stats \
  -H "X-API-Key: dev-api-key-change-in-production"
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Security Notes

- **No raw card data** is ever logged or returned in API responses.
- Sensitive card data is encrypted with **Fernet** (AES-128-CBC + HMAC-SHA256) before being stored.
- Transaction payloads are hashed with **SHA-256** for integrity verification.
- REST API endpoints are protected with **HMAC-SHA256** validated API keys.
- All secrets are loaded from **environment variables** — never hard-coded for production.
- Constant-time comparison (`hmac.compare_digest`) is used throughout to prevent timing attacks.
