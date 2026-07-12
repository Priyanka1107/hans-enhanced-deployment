#!/usr/bin/env bash
set -euo pipefail

echo "Starting PostgreSQL instance with Apptainer..."

# Create data directory if it doesn't exist
mkdir -p "$HOME/hans_pgdata"

# Pull PostgreSQL container
echo "Pulling PostgreSQL container..."
apptainer pull -F postgres16.sif docker://postgres:16

# Start PostgreSQL instance
echo "Starting PostgreSQL instance..."
apptainer instance start \
  --bind "$HOME/hans_pgdata:/var/lib/postgresql/data" \
  --env POSTGRES_PASSWORD=postgres \
  --env POSTGRES_DB=hans \
  postgres16.sif hans-pg

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Check if PostgreSQL is ready
if apptainer exec instance://hans-pg pg_isready -U postgres; then
    echo "✅ PostgreSQL instance 'hans-pg' started successfully"
    echo "📊 Data directory: $HOME/hans_pgdata"
else
    echo "❌ PostgreSQL instance failed to start properly"
    exit 1
fi