# HANS Apptainer Deployment Guide

This guide covers deploying HANS (HTW Berlin Student Services Assistant) using Apptainer containers on university infrastructure.

## Prerequisites

- Apptainer 1.1.3+ (`module load apptainer/1.1.3`)
- PostgreSQL data directory access (`$HOME/hans_pgdata`)
- University network access with proxy configuration
- No GPU required (CPU-only embeddings)

## Environment Setup

### 1. Configure Environment Variables

Copy and edit the environment configuration:

```bash
cp .env.example .env
```

Update `.env` with your settings:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/hans
OLLAMA_API_URL=https://f2ki-h100-1.f2.htw-berlin.de:11435/api/generate
OLLAMA_MODEL=llama3:8b
OLLAMA_TIMEOUT=300
VERIFY_SSL=false

# Network / proxy (already configured for HTW Berlin)
HTTP_PROXY=http://webproxy.rz.htw-berlin.de:3128
HTTPS_PROXY=http://webproxy.rz.htw-berlin.de:3128
NO_PROXY=localhost,127.0.0.1,141.45.161.0/16,141.45.161.106

# API server configuration
HANS_BIND=0.0.0.0
HANS_PORT=8080
```

### 2. Load Apptainer Module

```bash
module load apptainer/1.1.3
```

## Manual Deployment Steps

### Step 1: Build Application Container

```bash
./scripts/app_build.sif.sh
```

This creates `hans.sif` with all Python dependencies and applications.

### Step 2: Start PostgreSQL Instance

```bash
./scripts/pg_start.sif.sh
```

This pulls PostgreSQL 16 and starts a persistent instance with data in `$HOME/hans_pgdata`.

### Step 3: Initialize Database Schema

```bash
./scripts/pg_init.sif.sh
```

This creates the pgvector extension and database schema.

### Step 4: Ingest Content

```bash
./scripts/app_ingest_cpu.sif.sh
```

This processes web pages and Excel data into the database with CPU-only embeddings.

### Step 5: Test API Server

```bash
./scripts/app_api_start.sif.sh
```

This starts the FastAPI server on `0.0.0.0:8080` for staff access.

## Systemd Service Setup (Auto-start)

### Install User Services

```bash
# Copy service files to user systemd directory
mkdir -p ~/.config/systemd/user
cp systemd/*.service ~/.config/systemd/user/

# Update service files to match your deployment path
sed -i "s|%h/Hans_DB|$HOME/Hans_DB|g" ~/.config/systemd/user/*.service

# Reload systemd and enable services
systemctl --user daemon-reload
systemctl --user enable hans-pg.service
systemctl --user enable hans-api.service
```

### Start Services

```bash
# Start PostgreSQL
systemctl --user start hans-pg.service

# Start API server (will auto-start PostgreSQL if needed)
systemctl --user start hans-api.service
```

### Monitor Services

```bash
# Check service status
systemctl --user status hans-pg.service
systemctl --user status hans-api.service

# View logs
journalctl --user -u hans-api.service -f
journalctl --user -u hans-pg.service -f
```

## Application Usage

### Available Applications

The container provides four applications:

1. **ingest** - Build/update content database
   ```bash
   apptainer run --app ingest hans.sif --force
   ```

2. **console** - Interactive console interface
   ```bash
   apptainer run --app console hans.sif
   ```

3. **api** - HTTP API server (for staff access)
   ```bash
   apptainer run --app api hans.sif
   ```

4. **gui** - Tkinter GUI (requires X11/VNC)
   ```bash
   apptainer run --app gui hans.sif
   ```

### API Endpoints

- **Health Check**: `GET http://server:8080/health`
- **Ask Question**: `POST http://server:8080/ask`
  ```json
  {"q": "How do I apply to HTW Berlin?"}
  ```
- **Web Interface**: `GET http://server:8080/`
- **API Documentation**: `GET http://server:8080/docs`

### Example API Usage

```bash
# Health check
curl http://server:8080/health

# Ask a question
curl -X POST http://server:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"q": "What are the application deadlines?"}'
```

## Troubleshooting

### Database Issues

```bash
# Check PostgreSQL status
apptainer exec instance://hans-pg pg_isready -U postgres

# View database logs
journalctl --user -u hans-pg.service

# Restart database
systemctl --user restart hans-pg.service
```

### Network/Proxy Issues

```bash
# Test proxy connectivity
curl --proxy $HTTP_PROXY https://pypi.org/

# Check environment variables
apptainer exec hans.sif env | grep PROXY
```

### Container Issues

```bash
# Rebuild container
./scripts/app_build.sif.sh

# Test container applications
apptainer run hans.sif
apptainer run --app api hans.sif --help
```

### Model Download Issues

If embedding model download fails behind proxy:

```bash
# Pre-download models (run once)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"
```

## Security Notes

- Database binds to localhost only (secure)
- API server binds to 0.0.0.0:8080 for staff access
- No GPU access required (--nv flag not used)
- SSL verification disabled for Ollama (VERIFY_SSL=false)
- Services run in user space (no sudo required)
- Proxy settings respect university network policy

## Data Persistence

- **Database**: `$HOME/hans_pgdata` (PostgreSQL data directory)
- **Models**: `~/.cache/huggingface/` (embedding models)
- **Logs**: systemd journal (user space)

## Performance Notes

- **Embeddings**: CPU-only, ~4 texts/second
- **Memory**: ~4GB RAM recommended
- **Storage**: ~2GB for database and models
- **Network**: All outbound traffic via university proxy