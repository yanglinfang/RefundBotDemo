# Refund Bot - Project Handoff Document

## Project Overview

This project implements an **LLM-powered customer refund service** that demonstrates how to build an AI agent capable of handling refund requests through natural conversation. The bot understands customer intent, validates orders, and processes refunds automatically.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ Mock Orders │    │Mock Payments│    │       Ollama        │ │
│  │   :8001     │    │    :8002    │    │ (Local LLM) :11434  │ │
│  └──────▲──────┘    └──────▲──────┘    └──────────▲──────────┘ │
│         │                  │                      │             │
│         │                  │                      │             │
│  ┌──────┴──────────────────┴──────────────────────┴──────────┐ │
│  │                     Refund Bot :8000                       │ │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────────────┐   │ │
│  │  │ Chat API   │  │ Refund API │  │    LLM Client      │   │ │
│  │  └────────────┘  └────────────┘  │  (OpenAI-compat)   │   │ │
│  │                                   └────────────────────┘   │ │
│  │  ┌─────────────────────────────────────────────────────┐  │ │
│  │  │                   SQLite Database                    │  │ │
│  │  └─────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (Alternative: Cloud API)
                              ▼
                    ┌─────────────────────┐
                    │   OpenAI API        │
                    │ api.openai.com/v1   │
                    └─────────────────────┘
```

## What Has Been Completed

### 1. Mock Services for Refund Handling ✅

- **Mock Orders Service** (`services/mock-orders/`)
  - Simulates an order management system
  - Pre-seeded with test orders (ORD-001 through ORD-004)
  - Endpoints: GET /orders, GET /orders/{id}, POST /orders/{id}/cancel

- **Mock Payments Service** (`services/mock-payments/`)
  - Simulates a payment processing system
  - Handles refund creation and tracking
  - Endpoints: GET /payments/{id}, POST /refunds, GET /refunds/{id}

### 2. Core Refund Bot Service ✅

- **Conversation API** (`/api/v1/chat`)
  - Natural language interface for customers
  - Maintains conversation context across turns
  - Automatically detects refund intent and extracts order IDs

- **Refund API** (`/api/v1/refunds`)
  - Direct API for refund operations
  - Validates order eligibility (status, ownership, refund window)
  - Processes refunds through the payments service

### 3. LLM Integration - Two Approaches Tested ✅

#### Approach A: Cloud API (OpenAI)
```env
LLM_API_URL=https://api.openai.com/v1
LLM_API_KEY=sk-your-key-here
LLM_MODEL=gpt-4o-mini
```
- **Pros:** High quality responses, no local resources needed
- **Cons:** Requires API key, costs per token, network latency

#### Approach B: Local Ollama
```env
LLM_API_URL=http://ollama:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.2:1b
```
- **Pros:** Free, private, no external dependencies
- **Cons:** Requires local resources (~1.3GB for model), slightly lower quality

**Both approaches use the same OpenAI-compatible API format**, making them interchangeable.

### 4. LLM Router Implementation ✅

- Multi-endpoint routing with fallback/cost/latency/load strategies
- Health checks and metrics via `/health/llm`
- Automatic failover between endpoints
- Request/latency/failure tracking per endpoint

## Current State

The system is fully functional with configurable LLM routing between cloud and local backends:

```bash
# Start services
docker compose up -d

# Pull Ollama model (first time only)
docker compose exec ollama ollama pull llama3.2:1b

# Test the bot
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST-123", "message": "I want a refund for order ORD-001"}'
```

## Completed: LLM Router Implementation

The router now supports multi-endpoint routing with fallback, cost, latency, and load strategies, plus health checks per backend. Metrics are exposed at `/health/llm`.

## Test Data Reference

### Available Orders
| Order ID | Customer | Status | Amount | Refund Eligible |
|----------|----------|--------|--------|-----------------|
| ORD-001 | CUST-123 | delivered | $79.99 | Yes |
| ORD-002 | CUST-123 | shipped | $56.97 | Yes |
| ORD-003 | CUST-456 | pending | $49.99 | No (pending) |
| ORD-004 | CUST-789 | delivered | $129.99 | No (outside window) |

### Test Commands

```bash
# Health check all services
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health
# LLM router health
curl http://localhost:8000/health/llm

# Start a refund conversation
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST-123", "message": "I need a refund for ORD-001"}'

# Direct refund API
curl -X POST http://localhost:8000/api/v1/refunds \
  -H "Content-Type: application/json" \
  -d '{"order_id": "ORD-001", "customer_id": "CUST-123", "reason": "Defective"}'
```

## Project Structure

```
RefundBot/
├── docker-compose.yml      # Service orchestration
├── Dockerfile              # Main service container
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── .gitignore
│
├── src/                   # Main application
│   ├── main.py           # FastAPI entry point
│   ├── config.py         # Settings management
│   ├── database.py       # SQLite setup
│   ├── models/           # Database models
│   ├── routers/          # API endpoints
│   └── services/         # Business logic
│       ├── llm_client.py       # LLM client with router integration
│       ├── llm_router.py       # LLM routing + health
│       ├── conversation_service.py
│       ├── refund_service.py
│       ├── orders_client.py
│       └── payments_client.py
│
├── services/
│   ├── mock-orders/      # Mock order service
│   └── mock-payments/    # Mock payment service
│
├── scripts/              # Helper scripts
├── tests/                # Test files
└── data/                 # SQLite database location
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | sqlite+aiosqlite:///./data/refund_bot.db | Database connection |
| ORDERS_SERVICE_URL | http://mock-orders:8001 | Orders service URL |
| PAYMENTS_SERVICE_URL | http://mock-payments:8002 | Payments service URL |
| LLM_API_URL | http://ollama:11434/v1 | LLM endpoint |
| LLM_API_KEY | ollama | API key (empty for Ollama) |
| LLM_MODEL | llama3.2:1b | Model to use |
| LLM_ROUTER_STRATEGY | fallback | Routing strategy (single, fallback, cost, latency, load) |
| LLM_ENDPOINTS_JSON | (empty) | JSON array of LLM endpoints for routing |
| LLM_COMPLEXITY_THRESHOLD | 40 | Unique-word threshold to route to cloud |
| LLM_COMPLEXITY_CHAR_THRESHOLD | 800 | Character threshold to route to cloud |
| LLM_REQUEST_TIMEOUT_SECONDS | 20 | Timeout per LLM request before fallback |
| LOG_LEVEL | INFO | Logging level |

## Notes for Next Agent

1. The OpenAI client library works with both OpenAI and Ollama (OpenAI-compatible API)
2. Ollama model needs to be pulled separately after container starts
3. The `.env` file contains the actual API keys - never commit it
4. All services communicate via Docker network `refund-network`
5. The conversation service maintains state via SQLite - router metrics are tracked in memory
6. Use `/health/llm?refresh=true` to actively probe all endpoints

See `/health/llm` for router metrics and endpoint status.
