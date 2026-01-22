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

## Current State

The system is fully functional with manual switching between cloud and local LLM:

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

## Next Task: LLM Router Implementation

### Goal
Create an intelligent router that can dynamically choose between cloud and local LLM based on configurable criteria.

### Proposed Design

```
┌─────────────────────────────────────────────────────┐
│                   LLM Router                        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Request ──► Router Logic ──┬──► Local Ollama      │
│                             │                       │
│                             └──► Cloud OpenAI       │
│                                                     │
│  Routing Criteria:                                  │
│  - Fallback (local fails → cloud)                  │
│  - Cost-based (prefer local, cloud for complex)    │
│  - Latency-based (prefer fastest)                  │
│  - Load-based (distribute based on capacity)       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Suggested Implementation Steps

1. **Create `src/services/llm_router.py`**
   - Abstract base class for routing strategies
   - Implement routing strategies (fallback, cost-based, etc.)
   - Health checking for each LLM endpoint

2. **Update `src/config.py`**
   - Add configuration for multiple LLM endpoints
   - Add routing strategy selection
   ```python
   class LLMEndpoint(BaseModel):
       name: str
       url: str
       api_key: str
       model: str
       priority: int
       is_local: bool
   ```

3. **Update `src/services/llm_client.py`**
   - Integrate with router
   - Add retry logic with fallback
   - Add latency/cost tracking

4. **Add health check endpoint**
   - Monitor status of all LLM backends
   - Expose metrics (latency, success rate, cost)

### Key Files to Modify

| File | Purpose |
|------|---------|
| `src/services/llm_router.py` | NEW - Router implementation |
| `src/services/llm_client.py` | Integrate router, multi-endpoint support |
| `src/config.py` | Multi-endpoint configuration |
| `docker-compose.yml` | Environment variables for routing |
| `.env.example` | Document new configuration options |

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
│       ├── llm_client.py       # ← Modify for router
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
| LOG_LEVEL | INFO | Logging level |

## Notes for Next Agent

1. The OpenAI client library works with both OpenAI and Ollama (OpenAI-compatible API)
2. Ollama model needs to be pulled separately after container starts
3. The `.env` file contains the actual API keys - never commit it
4. All services communicate via Docker network `refund-network`
5. The conversation service maintains state via SQLite - consider if router decisions should be logged there

Good luck with the router implementation! 🚀
