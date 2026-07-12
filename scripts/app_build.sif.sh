#!/usr/bin/env bash
set -euo pipefail

echo "Building HANS Apptainer container..."

# Check if Singularity recipe exists
if [ ! -f "Singularity.hans" ]; then
    echo "❌ Singularity recipe not found: Singularity.hans"
    echo "Please ensure you're running this from the HANS project root"
    exit 1
fi

# Preserve proxy environment variables for the build
export HTTP_PROXY="${HTTP_PROXY:-}"
export HTTPS_PROXY="${HTTPS_PROXY:-}"
export NO_PROXY="${NO_PROXY:-}"

echo "🔧 Building container with proxy settings:"
echo "   HTTP_PROXY: ${HTTP_PROXY:-<not set>}"
echo "   HTTPS_PROXY: ${HTTPS_PROXY:-<not set>}"
echo "   NO_PROXY: ${NO_PROXY:-<not set>}"

# Build the container
echo "🏗️  Building hans.sif..."
apptainer build hans.sif Singularity.hans

if [ $? -eq 0 ]; then
    echo "✅ HANS container built successfully: hans.sif"
    echo "📦 Container size:"
    ls -lh hans.sif
    
    echo ""
    echo "🎯 Available applications:"
    echo "   apptainer run --app ingest hans.sif --force"
    echo "   apptainer run --app console hans.sif"
    echo "   apptainer run --app api hans.sif"
    echo "   apptainer run --app gui hans.sif"
else
    echo "❌ Container build failed"
    exit 1
fi