#!/usr/bin/env bash
set -euo pipefail

echo "Stopping PostgreSQL instance..."

# Stop the PostgreSQL instance
if apptainer instance stop hans-pg; then
    echo "✅ PostgreSQL instance 'hans-pg' stopped successfully"
else
    echo "⚠️  PostgreSQL instance 'hans-pg' was not running or failed to stop"
fi

# Optional: Clean up the SIF file (uncomment if desired)
# if [ -f "postgres16.sif" ]; then
#     rm postgres16.sif
#     echo "🗑️  Cleaned up postgres16.sif"
# fi

echo "💾 Data directory preserved: $HOME/hans_pgdata"