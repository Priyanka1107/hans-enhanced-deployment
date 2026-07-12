# Scapy Migration Pipeline

Complete end-to-end migration system for ingesting curated scapy objects into PostgreSQL with BGE embeddings.

## Overview

This pipeline replaces the old noisy knowledge base with 170 manually curated JSON objects. Key improvements:

- **Embedding model**: Switch from `intfloat/multilingual-e5-base` to `BAAI/bge-base-en-v1.5`
- **NO e5 prefixes**: Removes all "query:" and "passage:" prefixes
- **Embedding-time enrichment**: Builds richer text representation without modifying source JSON files
- **Smart chunking**: 1000-char chunks with sentence boundary detection
- **Thin hub enrichment**: Augments sparse objects with related content

## Architecture

```
scapy JSON objects
        ↓
   Load & Clean
        ↓
   Build Embedding Text
   (identity + signals + related + full_text)
        ↓
   Thin Hub Enrichment
   (borrow from related objects)
        ↓
   Chunking (1000 chars)
        ↓
   Embed with BGE
   (no prefixes)
        ↓
   Store in PostgreSQL
        ↓
   Vector Search + Reranking
```

## Files

### Core Modules

- **`text_cleaning.py`**: Removes breadcrumbs, headers, navigation artifacts
- **`signal_extraction.py`**: Extracts retrieval hints (dates, amounts, requirements)
- **`embedding_builder.py`**: Constructs enriched embedding text per object
- **`chunking.py`**: Smart chunking with sentence boundaries
- **`migrate_scapy_to_db.py`**: Main pipeline script

### Evaluation

- **`test_queries.json`**: 25 representative test queries
- **`evaluate_retrieval.py`**: Measures retrieval quality

## Installation

```bash
cd /Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy/scapy_migration

# Install dependencies
pip3 install sentence-transformers psycopg pyyaml
```

## Usage

### Step 1: Dry Run (Review Report)

```bash
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --report-csv migration_report.csv \
    --config ../config.yaml \
    --dry-run
```

This generates `migration_report.csv` showing:
- Object ID, type
- Text lengths before/after enrichment
- Whether object was enriched
- Whether still thin after enrichment
- Number of chunks created

**Review the report** to check:
- Objects with `still_thin_true_false = True` (may need manual inspection)
- Objects with very few chunks (< 2)
- Total chunks created (~680-1360 expected for 170 objects)

### Step 2: Run Full Migration

⚠️ **WARNING**: This will **truncate** existing `web_chunks` and `documents` tables.

```bash
# Backup database first!
pg_dump -h localhost -p 5433 -U hansuser hansdb > backup_before_migration.sql

# Run migration
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --report-csv migration_report.csv \
    --config ../config.yaml
```

Expected output:
```
INFO - Loading objects from ../scapy/htw_scrape/outputs/objects
INFO - Found 170 JSON files
INFO - Loaded 170 objects
INFO - Building enriched embedding text for all objects...
INFO - Report written with 170 rows
============================================================
MIGRATION SUMMARY
============================================================
Total objects processed: 170
Objects enriched with related content: ~30-50
Objects still thin after enrichment: ~5-15
Total chunks created: ~800-1200
Average chunks per object: 5.5
============================================================
INFO - Loading BGE embedding model...
INFO - Model loaded
INFO - Connecting to database...
INFO - Truncating web_chunks and documents tables...
INFO - Tables truncated
INFO - Embedding and storing chunks...
INFO - Created 170 document records
INFO - Stored 32/800 chunks
...
INFO - All chunks stored successfully
============================================================
MIGRATION COMPLETE
============================================================
```

### Step 3: Evaluate Retrieval Quality

```bash
python3 evaluate_retrieval.py \
    --queries test_queries.json \
    --config ../config.yaml \
    --output evaluation_results.json
```

This tests 25 queries and checks if correct object types appear in top-10 results.

Expected success rate: **70-85%** for well-curated objects.

## Configuration

### Chunk Size Tuning

Default settings:
- `chunk_chars`: 1000 (target chunk size)
- `chunk_overlap`: 200 (overlap between chunks)
- `min_chars`: 250 (minimum to keep)

To adjust:
```bash
python3 migrate_scapy_to_db.py \
    --chunk-chars 1200 \
    --chunk-overlap 250 \
    --min-chars 300 \
    ...
```

### Database Connection

The pipeline uses `config.yaml` for database connection:

```yaml
database:
  url: ${DATABASE_URL}
```

Ensure your `.env` or `.env.local` has:
```
DATABASE_URL=postgresql://hansuser:password@localhost:5433/hansdb
```

## Migration Report

The CSV report contains these columns:

| Column | Description |
|--------|-------------|
| `object_id` | Unique object identifier |
| `object_type` | One of 13 types (degree_program, application_process, etc.) |
| `cleaned_full_text_len` | Length after removing breadcrumbs |
| `embedding_text_len_before_enrich` | Length with identity + signals + full_text |
| `embedding_text_len_after_enrich` | Length after borrowing from related objects |
| `enriched_true_false` | Whether object was enriched |
| `still_thin_true_false` | Whether still thin after enrichment |
| `num_chunks` | Number of chunks created |

### Flags to Review

**Objects to manually inspect:**
```bash
# Find still-thin objects
grep "True" migration_report.csv | grep "still_thin"

# Find objects with < 2 chunks
awk -F',' '$8 < 2' migration_report.csv
```

## Troubleshooting

### Issue: "No objects loaded"

**Cause**: Wrong path to objects directory

**Fix**:
```bash
ls ../scapy/htw_scrape/outputs/objects/*.json | wc -l
# Should show 170
```

### Issue: "Database connection failed"

**Cause**: PostgreSQL not running or wrong credentials

**Fix**:
```bash
# Check if DB is running
docker ps | grep postgres

# Test connection
psql -h localhost -p 5433 -U hansuser -d hansdb -c "SELECT 1"
```

### Issue: "Model download failed"

**Cause**: Internet connection or HuggingFace down

**Fix**:
```bash
# Pre-download models
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-base-en-v1.5')"
```

### Issue: Low evaluation success rate (< 60%)

**Possible causes**:
1. Chunks too small/large → Adjust `--chunk-chars`
2. Objects too thin → Check report for `still_thin` flags
3. Reranker not working → Check logs for reranker errors

**Debug**:
```bash
# Check chunk size distribution
awk -F',' '{sum+=$8; count++} END {print sum/count}' migration_report.csv

# Should be 4-8 chunks per object on average
```

## Next Steps

After successful migration:

1. **Update retrieval code** to remove e5 prefixes:
   ```python
   # OLD (with e5)
   query_embedding = embed_query(f"query: {user_query}")

   # NEW (BGE, no prefix)
   query_embedding = embed_query(user_query)
   ```

2. **Update config.yaml**:
   ```yaml
   model:
     embedding_model: BAAI/bge-base-en-v1.5  # Changed from multilingual-e5-base
     embedding_dim: 768
   ```

3. **Test end-to-end**:
   ```bash
   # Run API and test with real queries
   python3 htw_assistant_api.py

   # Send test query
   curl -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"q": "What is the semester fee?", "max_sources": 10}'
   ```

4. **Compare old vs new** (if old embeddings available):
   - Run evaluation on both
   - Compare success rates
   - Inspect quality of retrieved chunks

## Design Decisions & Assumptions

### Why BGE instead of E5?

- BGE is trained without prefixes, more natural
- Better performance on general retrieval tasks
- Simpler to use (no prefix management)

### Why 1000-char chunks?

- Balance between precision (smaller) and context (larger)
- 800 chars (old config) was too small for enriched text
- 1800 chars (original config) was too large, caused noise

### Why enrich at embedding-time?

- **PRO**: Don't modify source JSON files (keep them clean)
- **PRO**: Easy to iterate on enrichment logic
- **CON**: Can't query structured fields directly (but that's future MCP work)

### Why truncate tables?

- Simplest migration strategy
- Old data is noisy, full replacement is cleaner
- Can implement incremental update later if needed

## Performance

Expected performance on typical hardware:

- **Loading objects**: < 5 seconds
- **Building embedding text**: ~30 seconds
- **Chunking**: ~5 seconds
- **Embedding 1000 chunks**: ~30 seconds (GPU) or ~3 minutes (CPU)
- **Storing in DB**: ~10 seconds
- **Total migration time**: ~1-4 minutes

Evaluation (25 queries):
- **Embedding queries**: ~5 seconds
- **Vector search**: ~2 seconds
- **Reranking**: ~3 seconds
- **Total**: ~10 seconds

## Contact

For questions or issues, refer to the main HANS documentation or the enrichment assessment reports in the `scapy/htw_scrape/outputs/objects/` directory.
