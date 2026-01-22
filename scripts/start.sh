#!/bin/bash
# Quick start script for the Refund Bot demo

set -e

echo "Starting Refund Bot Demo..."
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker Desktop first."
  exit 1
fi

# Copy .env if it doesn't exist
if [ ! -f .env ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

# Build and start services
echo "Building and starting services..."
docker compose up --build -d

echo ""
echo "Waiting for services to start..."
sleep 5

# Health check
echo ""
echo "Checking service health..."
curl -s http://localhost:8000/health || echo "Refund Bot not ready yet"
curl -s http://localhost:8001/health || echo "Orders service not ready yet"
curl -s http://localhost:8002/health || echo "Payments service not ready yet"

echo ""
echo "================================"
echo "Services are starting!"
echo ""
echo "Endpoints:"
echo "  - Refund Bot:     http://localhost:8000"
echo "  - Mock Orders:    http://localhost:8001"
echo "  - Mock Payments:  http://localhost:8002"
echo ""
echo "API Docs:           http://localhost:8000/docs"
echo ""
echo "To test the flow:   ./scripts/test_refund_flow.sh"
echo "To view logs:       docker compose logs -f"
echo "To stop:            docker compose down"
echo "================================"
