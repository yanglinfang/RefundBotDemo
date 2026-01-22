#!/bin/bash
# Setup script for Ollama model
# Run this after docker compose up to pull the model

set -e

MODEL="${1:-llama3.2:1b}"

echo "Waiting for Ollama to be ready..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
  echo "Waiting for Ollama..."
  sleep 2
done

echo "Ollama is ready. Pulling model: $MODEL"
docker compose exec ollama ollama pull "$MODEL"

echo ""
echo "Model $MODEL is ready!"
echo "You can now test the refund bot."
