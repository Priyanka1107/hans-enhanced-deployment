# HTW Berlin Student Services Bot - Database Implementation

## Overview

This is an AI-powered student services assistant for HTW Berlin that uses PostgreSQL with pgvector for scalable semantic search and retrieval. The system has been migrated from FAISS/pickle-based storage to a database-backed architecture for better performance, scalability, and maintainability.

## Key Features

- ✅ **Database-Backed RAG**: PostgreSQL + pgvector for vector similarity search
- ✅ **Local Embeddings**: BAAI/bge-base-en-v1.5 model for consistent embeddings
- ✅ **Scalable Storage**: Web chunks and Q&A pairs stored in database with metadata
- ✅ **Fast Retrieval**: IVFFLAT indexes for efficient cosine similarity search
- ✅ **Smart Responses**: llama3:8b generates contextual responses
- ✅ **Comprehensive Ingestion**: Automated web content and Excel Q&A processing
- ✅ **Schema Versioning**: Database migration support and validation

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   User Query    │───▶│  Local Embedding │───▶│ PostgreSQL+pgvector │
│                 │    │  BAAI/bge-base   │    │ Vector Search       │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
                                                           │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────────┐
│   Response      │◀───│  Chat Generation │◀───│ Retrieved Chunks    │
│   Display       │    │  llama3:8b       │    │ + Metadata          │
└─────────────────┘    └──────────────────┘    └─────────────────────┘
```

## Database Setup

### Prerequisites
- PostgreSQL 12+ with pgvector extension
- Python 3.8+ with required packages
- 4GB+ RAM (8GB+ recommended)
- 2GB+ free storage

### Step 1: Install PostgreSQL and pgvector
```bash
# Install PostgreSQL (example for Ubuntu)
sudo apt-get install postgresql postgresql-contrib

# Install pgvector (varies by system)
# See: https://github.com/pgvector/pgvector#installation
```

### Step 2: Create Database
```bash
# Create database
createdb hans

# Enable pgvector extension
psql -d hans -c "CREATE EXTENSION vector;"
```

### Step 3: Configure Environment
```bash
# Copy and edit environment file
cp .env.example .env

# Edit DATABASE_URL in .env
# DATABASE_URL=postgresql://username:password@localhost:5432/hans
```

### Step 4: Set Up Database Schema
```bash
# Run database schema setup
psql "$DATABASE_URL" -f db/ddl.sql
```

### Step 5: Build Content Database
```bash
# Install Python dependencies
pip install -r requirements.txt

# Build database from web JSON and Excel data
python scripts/build_content_db.py

# Force rebuild (if needed)
python scripts/build_content_db.py --force

# Build only web content
python scripts/build_content_db.py --only web

# Build only Excel Q&A
python scripts/build_content_db.py --only excel
```

### Step 6: Validate Setup
```bash
# Run validation tests
python scripts/validate_db.py
```

### Step 7: Launch Application
```bash
# Launch with database backend
python launch_assistant_db.py
```

## Model Requirements

### Local Embedding Model
- **Model**: BAAI/bge-base-en-v1.5
- **Size**: ~400MB (automatically downloaded)
- **Performance**: 4 texts/second on CPU
- **Memory**: < 1GB peak usage
- **Download**: Automatic on first run (2-5 minutes)

### Remote Chat Model
- **Model**: llama3:8b
- **Server**: HTW Berlin Ollama server
- **URL**: https://f2ki-h100-1.f2.htw-berlin.de:11435
- **Initial Load**: 2-3 minutes (one-time)
- **Subsequent Requests**: Fast response generation

## Configuration Files

### config.yaml
Main configuration file with database, model, and retrieval settings:

```yaml
schema_version: 1
database:
  url: ${DATABASE_URL}
paths:
  web_json_dir: scrape/htw_student_data
  excel_path: HANS - Training Email Data.xlsx
model:
  embedding_model: BAAI/bge-base-en-v1.5
  embedding_dim: 768
retrieval:
  top_k: 6
  distance: cosine
runtime:
  ollama_model: llama3:8b
```

### .env
Environment variables for database connection:

```bash
DATABASE_URL=postgresql://username:password@localhost:5432/hans
```

## Usage

### Database Operations

#### Initial Content Ingestion
After setting up the database, populate it with content:

```bash
# Full ingestion (web + Excel)
python scripts/build_content_db.py

# Force rebuild all content
python scripts/build_content_db.py --force

# Dry run to see what would be processed
python scripts/build_content_db.py --dry-run

# Process only web content
python scripts/build_content_db.py --only web

# Process only Excel Q&A
python scripts/build_content_db.py --only excel
```

#### After New Data
When you have new web scrapes or updated Excel files:

```bash
# Re-run ingestion to add new content
python scripts/build_content_db.py

# Force full rebuild if needed
python scripts/build_content_db.py --force
```

### Application Usage
1. **Start Application**: Run `python launch_assistant_db.py`
2. **Database Check**: System validates database connection and schema
3. **Interface Choice**: Select GUI or console interface
4. **Query Processing**: Enter questions and get responses with source metadata
5. **Automatic Retrieval**: System finds relevant content using vector similarity

### Example Queries
- "What are the language requirements for international students?"
- "How do I apply for a student visa?"
- "What are the tuition fees for master's programs?"
- "How can I register for courses?"

## File Structure

```
HANS Database Version/
├── config.yaml                    # Main configuration
├── .env                          # Environment variables
├── launch_assistant_db.py        # Database-backed launcher
├── hans_db_agents.py             # Database RAG agents
├── hansdb/                       # Database package
│   ├── __init__.py
│   ├── conn.py                   # Database connections
│   ├── embeddings.py             # Embedding management
│   └── retrieval.py              # Vector search & retrieval
├── db/
│   └── ddl.sql                   # Database schema
├── scripts/
│   ├── build_content_db.py       # Content ingestion
│   └── validate_db.py            # System validation
├── scrape/htw_student_data/      # Web JSON content
├── HANS - Training Email Data.xlsx  # Q&A training data
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── mcp_agents.py                 # Legacy FAISS system (preserved)
├── mcp_config.py                 # Legacy configuration
└── pages/                        # Legacy web pages (preserved)
```

## Database Schema

The system uses PostgreSQL with pgvector extension for vector storage and similarity search:

### Tables
- **documents**: Web pages and Excel sources with metadata
- **web_chunks**: Text chunks from web pages with embeddings and contacts/links
- **qa_pairs**: Question-answer pairs from Excel with question embeddings
- **meta**: Schema version tracking

### Vector Indexes
- **IVFFLAT indexes** on embeddings for fast cosine similarity search
- **Optimized for 768-dimensional** BGE embeddings

## Error Handling

### Common Issues
1. **Database Connection Failed**
   - Check DATABASE_URL in .env
   - Verify PostgreSQL is running
   - Ensure database exists

2. **Schema Version Mismatch**
   - Run `python scripts/build_content_db.py --force`

3. **No Content Found**
   - Check web JSON files exist in `scrape/htw_student_data/`
   - Verify Excel file exists: `HANS - Training Email Data.xlsx`
   - Run ingestion: `python scripts/build_content_db.py`

4. **pgvector Extension Missing**
   - Install pgvector extension
   - Run `CREATE EXTENSION vector;` in your database

### Performance Settings
- **Embedding Model**: BAAI/bge-base-en-v1.5 (local)
- **Chat Model**: llama3:8b (remote)
- **Similarity Threshold**: 0.65 (configurable)
- **Max Snippets**: 5 (configurable)
- **Cache Size**: 100 embeddings (dynamic)

## Troubleshooting

### Common Issues

#### 1. Model Download Fails
**Problem**: BAAI/bge-base-en-v1.5 download fails
**Solution**: 
```bash
# Manual download
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"
```

#### 2. Ollama Server Connection Fails
**Problem**: Cannot connect to llama3:8b server
**Solution**:
- Check internet connection
- Verify server URL in `mcp_config.py`
- Use "Test Connection" button in GUI

#### 3. First Request Times Out
**Problem**: Initial request takes too long
**Solution**: 
- Wait for model pre-warming to complete
- Check status bar for "Ready - Model pre-warmed"
- Increase timeout in `mcp_config.py` if needed

#### 4. Memory Issues
**Problem**: Application uses too much memory
**Solution**:
- Close other applications
- Restart the application
- Check available RAM (8GB+ recommended)

### Performance Optimization

#### For Faster Startup
- Keep the application running (don't restart frequently)
- Model pre-warming happens automatically
- Pre-computed embeddings load instantly

#### For Better Performance
- Use SSD storage for faster model loading
- Ensure adequate RAM (8GB+ recommended)
- Close unnecessary applications

## Development

### Adding New Content
1. Add new text files to `pages/` directory
2. Run `python3 embed_pages_local.py` to regenerate embeddings
3. Restart the application

### Modifying Models
1. Update model name in `mcp_config.py`
2. Update model name in `embed_pages_local.py`
3. Regenerate embeddings with new model
4. Test performance and quality

### Extending Functionality
- Add new agents in `mcp_agents.py`
- Modify prompts in `mcp_config.py`
- Update GUI in `htw_assistant_gui_simple.py`

## Performance Metrics

### Current Performance
- **Embedding Speed**: 4 texts/second
- **Query Response**: ~50ms for similarity search
- **Model Loading**: 2.5 minutes (one-time)
- **Memory Usage**: < 1GB peak
- **Storage**: ~400MB for embedding model

### Scalability
- **Web Pages**: 256+ (easily expandable)
- **Training Data**: 105 Q&A pairs
- **Cache Efficiency**: 100+ embeddings cached
- **Response Quality**: High with llama3:8b

## Support

### Logs
- Application logs: `htw_assistant.log`
- Console output: Detailed error messages
- GUI status: Real-time status updates

### Debugging
- Use "Test Connection" button
- Check console output for detailed errors
- Verify model files are downloaded
- Test with simple queries first

## License

This project is developed for HTW Berlin Student Services.

## Contributors

- HTW Berlin Student Services Team
- AI Implementation: Local embedding replacement for improved performance

---

**Last Updated**: June 26, 2025  
**Version**: 1.0  
**Status**: ✅ Production Ready