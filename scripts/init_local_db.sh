#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Initializing local HANS database..."

# Check if DATABASE_URL is set
if [ -z "${DATABASE_URL:-}" ]; then
    echo "❌ ERROR: DATABASE_URL environment variable not set"
    echo ""
    echo "Please run:"
    echo "  export \$(grep -v '^#' .env.local | xargs)"
    echo "  bash scripts/init_local_db.sh"
    exit 1
fi

echo "📍 Database URL: ${DATABASE_URL}"

# Check if psql is available
if ! command -v psql &> /dev/null; then
    echo "❌ ERROR: psql command not found"
    echo "Please install PostgreSQL client tools"
    exit 1
fi

# Test database connection
echo "🔌 Testing database connection..."
if ! psql "${DATABASE_URL}" -c "SELECT 1" > /dev/null 2>&1; then
    echo "❌ ERROR: Cannot connect to database"
    echo "Make sure the database is running:"
    echo "  bash scripts/start_local_db.sh"
    exit 1
fi
echo "✅ Database connection successful"

# Enable pgvector extension
echo "📦 Enabling pgvector extension..."
psql "${DATABASE_URL}" -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
    echo "❌ ERROR: Failed to create pgvector extension"
    exit 1
}
echo "✅ pgvector extension enabled"

# Apply schema from DDL
echo "📋 Applying database schema from db/ddl.sql..."
if [ ! -f "db/ddl.sql" ]; then
    echo "❌ ERROR: Schema file not found: db/ddl.sql"
    echo "Make sure you're running this from the baseline_copy directory"
    exit 1
fi

psql "${DATABASE_URL}" -f db/ddl.sql || {
    echo "❌ ERROR: Failed to apply schema"
    exit 1
}
echo "✅ Schema applied successfully"

# Run content ingestion
echo "📚 Running content ingestion (this may take a few minutes)..."
echo ""

# Check if Python script exists
if [ ! -f "scripts/build_content_db.py" ]; then
    echo "❌ ERROR: Ingestion script not found: scripts/build_content_db.py"
    exit 1
fi

python scripts/build_content_db.py --force || {
    echo "❌ ERROR: Content ingestion failed"
    exit 1
}

echo ""
echo "✅ Local database initialization complete!"
echo ""
echo "📊 Database summary:"
psql "${DATABASE_URL}" -c "SELECT
    (SELECT COUNT(*) FROM documents) as documents,
    (SELECT COUNT(*) FROM web_chunks) as web_chunks,
    (SELECT COUNT(*) FROM qa_pairs) as qa_pairs;"

echo ""
echo "🚀 Next steps:"
echo "  1. Start the API server:"
echo "     python api_server.py"
echo ""
echo "  2. Run experiments:"
echo "     python experiments/run_experiments.py"
