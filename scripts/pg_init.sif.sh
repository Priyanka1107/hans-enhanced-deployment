#!/usr/bin/env bash
set -euo pipefail

echo "Initializing PostgreSQL database for HANS..."

# Check if PostgreSQL instance is running
if ! apptainer exec instance://hans-pg pg_isready -U postgres; then
    echo "❌ PostgreSQL instance 'hans-pg' is not running"
    echo "Please run pg_start.sif.sh first"
    exit 1
fi

# Create vector extension
echo "Creating pgvector extension..."
apptainer exec instance://hans-pg psql -U postgres -d hans -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Check if DDL file exists
if [ ! -f "db/ddl.sql" ]; then
    echo "❌ DDL file not found: db/ddl.sql"
    echo "Please ensure you're running this from the HANS project root"
    exit 1
fi

# Execute DDL to create schema
echo "Creating database schema..."
apptainer exec instance://hans-pg psql -U postgres -d hans < db/ddl.sql

# Verify schema creation
echo "Verifying schema creation..."
TABLE_COUNT=$(apptainer exec instance://hans-pg psql -U postgres -d hans -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
TABLE_COUNT=$(echo $TABLE_COUNT | tr -d ' ')

if [ "$TABLE_COUNT" -ge 3 ]; then
    echo "✅ Database schema initialized successfully"
    echo "📋 Tables created: $TABLE_COUNT"
    
    # Show table summary
    echo "📊 Database tables:"
    apptainer exec instance://hans-pg psql -U postgres -d hans -c "\dt"
else
    echo "❌ Schema initialization may have failed"
    echo "Expected at least 3 tables, found: $TABLE_COUNT"
    exit 1
fi