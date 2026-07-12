# Schema V2 Quick Reference

## Database Connection
```bash
psql -h 127.0.0.1 -p 5433 -U postgres -d hans
# Password: postgres
```

## Quick Stats
```sql
-- Document count (should be 170)
SELECT COUNT(*) FROM hans_v2.documents;

-- Chunk count (should be 930)
SELECT COUNT(*) FROM hans_v2.chunks;

-- Average chunks per document
SELECT AVG(chunk_count)::numeric(10,2) as avg_chunks
FROM (
    SELECT document_id, COUNT(*) as chunk_count
    FROM hans_v2.chunks
    GROUP BY document_id
) x;
```

## Common Queries

### Find Documents
```sql
-- By type
SELECT object_id, title, url
FROM hans_v2.documents
WHERE object_type = 'application_process'
LIMIT 10;

-- By object_id
SELECT * FROM hans_v2.documents
WHERE object_id = 'accessibility_support-barrier-free-campus';

-- All document types
SELECT object_type, COUNT(*) as count
FROM hans_v2.documents
GROUP BY object_type
ORDER BY count DESC;
```

### Find Chunks
```sql
-- Chunks for specific document
SELECT c.chunk_index, c.chunk_text, c.chunk_text_len
FROM hans_v2.chunks c
JOIN hans_v2.documents d ON c.document_id = d.id
WHERE d.object_id = 'accessibility_support-barrier-free-campus'
ORDER BY c.chunk_index;

-- Documents with most chunks
SELECT d.object_id, d.title, COUNT(*) as chunk_count
FROM hans_v2.chunks c
JOIN hans_v2.documents d ON c.document_id = d.id
GROUP BY d.id, d.object_id, d.title
ORDER BY chunk_count DESC
LIMIT 10;

-- Enriched chunks
SELECT d.object_id, COUNT(*) as enriched_chunks
FROM hans_v2.chunks c
JOIN hans_v2.documents d ON c.document_id = d.id
WHERE c.enriched = true
GROUP BY d.object_id;
```

## Vector Search Template

```python
from sentence_transformers import SentenceTransformer
import psycopg

# Load model
model = SentenceTransformer('BAAI/bge-base-en-v1.5')

# Generate query embedding (NO PREFIX for BGE!)
query = "What is the semester fee?"
query_embedding = model.encode(query, normalize_embeddings=True)

# Connect to DB
conn = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:5433/hans")

# Set ivfflat probes
with conn.cursor() as cur:
    cur.execute("SET ivfflat.probes = 10")

    # Vector search
    cur.execute("""
        SELECT
            d.object_id,
            d.title,
            d.url,
            c.chunk_text,
            c.embedding <=> %s::vector as distance
        FROM hans_v2.chunks c
        JOIN hans_v2.documents d ON c.document_id = d.id
        ORDER BY c.embedding <=> %s::vector
        LIMIT 30
    """, (query_embedding.tolist(), query_embedding.tolist()))

    results = cur.fetchall()

conn.close()
```

## Maintenance

### Optimize Index
```sql
-- After inserting/updating data
ANALYZE hans_v2.chunks;

-- Rebuild index if needed
DROP INDEX IF EXISTS hans_v2.idx_chunks_embedding_ivfflat;
CREATE INDEX idx_chunks_embedding_ivfflat
ON hans_v2.chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Adjust Performance
```sql
-- Increase recall (slower)
SET ivfflat.probes = 20;

-- Decrease latency (lower recall)
SET ivfflat.probes = 5;

-- Default
SET ivfflat.probes = 10;
```

## Truncate and Remigrate
```bash
# Truncate v2 tables
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d hans << 'EOF'
TRUNCATE TABLE hans_v2.chunks CASCADE;
TRUNCATE TABLE hans_v2.documents CASCADE;
EOF

# Run migration
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --config ../config.yaml

# Optimize
PGPASSWORD=postgres psql -h 127.0.0.1 -p 5433 -U postgres -d hans -c "ANALYZE hans_v2.chunks;"
```

## Table Schema

### hans_v2.documents
- **id** (BIGSERIAL PK) - Auto-increment document ID
- **object_id** (TEXT UNIQUE) - Scapy object identifier
- **object_type** (TEXT) - Type classification
- **url** (TEXT) - Source URL
- **title** (TEXT) - Page title
- **page_id** (TEXT) - Page hash
- **last_scraped** (DATE) - Scrape date
- **last_processed** (TIMESTAMPTZ) - Processing timestamp
- **classification_confidence** (TEXT) - Confidence level
- **classification_notes** (TEXT) - Classification notes
- **related_pages** (JSONB) - Array of related object IDs
- **raw_json** (JSONB) - Full original object
- **created_at** (TIMESTAMPTZ) - Insert timestamp

### hans_v2.chunks
- **id** (BIGSERIAL PK) - Auto-increment chunk ID
- **document_id** (BIGINT FK) - References documents(id)
- **chunk_index** (INT) - Sequential index within document
- **chunk_text** (TEXT) - Chunk content
- **chunk_text_len** (INT) - Length in characters
- **enriched** (BOOLEAN) - Was document enriched?
- **still_thin** (BOOLEAN) - Still thin after enrichment?
- **embedding** (vector(768)) - BGE embedding
- **created_at** (TIMESTAMPTZ) - Insert timestamp

## Files
- **schema_v2.sql** - Schema definition
- **migrate_scapy_to_db.py** - Migration script
- **SCHEMA_V2_MIGRATION_COMPLETE.md** - Full documentation
- **migration_report_v2.csv** - Per-object statistics

## Status
✅ Migration complete: 170 documents, 930 chunks
✅ Embeddings: 768 dims (BGE)
✅ Indexes: All created and optimized
✅ Old schema: Untouched (rollback safe)
