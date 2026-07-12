#!/usr/bin/env bash
set -euo pipefail

echo "Starting HANS API server..."

# Check if container exists
if [ ! -f "hans.sif" ]; then
    echo "❌ Container not found: hans.sif"
    echo "Please run app_build.sif.sh first"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ Environment file not found: .env"
    echo "Please create .env from .env.example and configure it"
    exit 1
fi

# Load environment variables
echo "📋 Loading environment from .env..."
export $(grep -v '^[# ]' .env | xargs) || true

# Set API server defaults for staff access
export HANS_BIND=${HANS_BIND:-"0.0.0.0"}
export HANS_PORT=${HANS_PORT:-"8080"}

echo "🌐 Starting API server:"
echo "   Bind address: ${HANS_BIND}:${HANS_PORT}"
echo "   Database: ${DATABASE_URL}"
echo "   Ollama: ${OLLAMA_API_URL}"
echo "   Proxy: ${HTTP_PROXY:-<not set>}"

# Start API server
apptainer run \
  --env OLLAMA_API_URL \
  --env OLLAMA_MODEL \
  --env OLLAMA_TIMEOUT \
  --env VERIFY_SSL \
  --env DATABASE_URL \
  --env HTTP_PROXY \
  --env HTTPS_PROXY \
  --env NO_PROXY \
  --env HANS_BIND \
  --env HANS_PORT \
  --app api \
  hans.sif