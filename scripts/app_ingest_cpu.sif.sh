#!/usr/bin/env bash
set -euo pipefail

echo "Running HANS content ingestion (CPU-only)..."

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

# Verify required environment variables
REQUIRED_VARS=(
    "DATABASE_URL"
    "OLLAMA_API_URL"
    "OLLAMA_MODEL"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "❌ Required environment variable not set: $var"
        exit 1
    fi
done

echo "🔧 Environment configured:"
echo "   DATABASE_URL: ${DATABASE_URL}"
echo "   OLLAMA_API_URL: ${OLLAMA_API_URL}"
echo "   OLLAMA_MODEL: ${OLLAMA_MODEL}"
echo "   HTTP_PROXY: ${HTTP_PROXY:-<not set>}"

# Run content ingestion
echo "🏗️  Starting content ingestion..."
apptainer run \
  --env OLLAMA_API_URL \
  --env OLLAMA_MODEL \
  --env OLLAMA_TIMEOUT \
  --env VERIFY_SSL \
  --env DATABASE_URL \
  --env HTTP_PROXY \
  --env HTTPS_PROXY \
  --env NO_PROXY \
  --app ingest \
  hans.sif "$@"

if [ $? -eq 0 ]; then
    echo "✅ Content ingestion completed successfully"
else
    echo "❌ Content ingestion failed"
    exit 1
fi