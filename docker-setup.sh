#!/bin/bash
# HANS Docker Setup Script
# This script sets up the complete HANS database system using Docker

set -e  # Exit on any error

echo "🚀 Setting up HANS Database System with Docker"
echo "=" * 50

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✅ Docker is running"

# Stop any existing containers
echo "🧹 Stopping any existing HANS containers..."
docker-compose down 2>/dev/null || true

# Start PostgreSQL with pgvector
echo "🐘 Starting PostgreSQL with pgvector extension..."
docker-compose up -d postgres

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
timeout 60s bash -c 'until docker-compose exec postgres pg_isready -U hans -d hans; do sleep 2; done'

if [ $? -eq 0 ]; then
    echo "✅ Database is ready!"
else
    echo "❌ Database startup timeout. Check logs with: docker-compose logs postgres"
    exit 1
fi

# Verify pgvector extension
echo "🔧 Verifying pgvector extension..."
docker-compose exec postgres psql -U hans -d hans -c "SELECT extname FROM pg_extension WHERE extname = 'vector';" | grep -q vector
if [ $? -eq 0 ]; then
    echo "✅ pgvector extension is installed"
else
    echo "❌ pgvector extension not found"
    exit 1
fi

# Show database status
echo "📊 Database Status:"
docker-compose exec postgres psql -U hans -d hans -c "\dt"

echo ""
echo "🎉 Docker setup complete!"
echo ""
echo "Next steps:"
echo "1. Install Python dependencies: pip install -r requirements.txt"
echo "2. Build content database: python scripts/build_content_db.py"
echo "3. Launch HANS: python launch_assistant_db.py"
echo ""
echo "Useful commands:"
echo "- View logs: docker-compose logs -f postgres"
echo "- Connect to DB: docker-compose exec postgres psql -U hans -d hans"
echo "- Stop database: docker-compose down"
echo "- Reset database: docker-compose down -v && docker-compose up -d"