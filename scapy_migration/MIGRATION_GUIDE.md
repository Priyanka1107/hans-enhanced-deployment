# Quick Start Migration Guide

## Prerequisites

1. PostgreSQL running on port 5433
2. Python 3.8+ with required packages
3. Scapy objects directory at `../scapy/htw_scrape/outputs/objects/`

## Step-by-Step Migration

### 1. Verify Prerequisites

```bash
# Check PostgreSQL
docker ps | grep postgres
# Should show container running on 5433:5432

# Check Python packages
pip3 list | grep -E "sentence-transformers|psycopg|pyyaml"

# Check scapy objects
ls ../scapy/htw_scrape/outputs/objects/*.json | wc -l
# Should show 170
```

### 2. Backup Current Database

```bash
# Create backup
pg_dump -h localhost -p 5433 -U hansuser hansdb > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup
ls -lh backup_*.sql
```

### 3. Run Dry Run

```bash
cd /Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy/scapy_migration

python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --report-csv migration_report.csv \
    --config ../config.yaml \
    --dry-run
```

**Review `migration_report.csv`:**
- Check `still_thin_true_false` column (should be < 10% True)
- Check `num_chunks` column (average should be 4-8)
- Look for anomalies (objects with 0 chunks, excessive enrichment)

### 4. Run Full Migration

```bash
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --report-csv migration_report.csv \
    --config ../config.yaml
```

Expected duration: **1-4 minutes**

### 5. Verify Migration

```bash
# Check database
psql -h localhost -p 5433 -U hansuser -d hansdb -c "
SELECT COUNT(*) as num_docs FROM documents;
SELECT COUNT(*) as num_chunks FROM web_chunks;
"

# Expected:
# num_docs: 170
# num_chunks: 800-1200
```

### 6. Evaluate Retrieval

```bash
python3 evaluate_retrieval.py \
    --queries test_queries.json \
    --config ../config.yaml \
    --output evaluation_results.json
```

Expected success rate: **70-85%**

### 7. Update Application Code

**a) Update config.yaml** (if using root config):

```yaml
model:
  embedding_model: BAAI/bge-base-en-v1.5  # Changed from multilingual-e5-base
  embedding_dim: 768
```

**b) Remove e5 prefixes from code:**

Find and update files that use e5 prefixes:
```bash
grep -r "query:" ../hansdb/ ../scripts/
grep -r "passage:" ../hansdb/ ../scripts/
```

Update embeddings code to NOT add prefixes:
```python
# OLD
def embed_query(text):
    return model.encode(f"query: {text}")

# NEW
def embed_query(text):
    return model.encode(text)  # NO prefix for BGE
```

### 8. Test End-to-End

```bash
# Start API server
cd ..
python3 htw_assistant_api.py

# In another terminal, test query
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"q": "What is the semester fee at HTW Berlin?", "max_sources": 10}'
```

Expected response should cite semester fee information (€357.30).

## Rollback Procedure

If migration fails or results are poor:

```bash
# Stop API server
# Ctrl+C in API terminal

# Restore backup
psql -h localhost -p 5433 -U hansuser -d hansdb < backup_YYYYMMDD_HHMMSS.sql

# Revert config changes
git checkout config.yaml  # if using git

# Restart API with old config
python3 htw_assistant_api.py
```

## Troubleshooting

### Migration fails with "No objects loaded"

**Solution**: Check path to objects directory
```bash
ls -la ../scapy/htw_scrape/outputs/objects/
```

### Migration fails with "Database connection failed"

**Solution**: Check PostgreSQL and credentials
```bash
# Check if running
docker ps | grep postgres

# Check connection
psql -h localhost -p 5433 -U hansuser -d hansdb -c "SELECT 1"

# Check .env file
cat ../.env.local | grep DATABASE_URL
```

### Evaluation shows low success rate (< 60%)

**Solutions**:
1. Check if chunks are too small: `awk -F',' '{print $8}' migration_report.csv | sort -n | head -20`
2. Increase chunk size: Run with `--chunk-chars 1200`
3. Check thin objects: `grep "True" migration_report.csv | grep "still_thin"`

### API returns irrelevant results

**Solutions**:
1. Verify BGE model is loaded (check logs for "Loading BGE embedding model")
2. Ensure no e5 prefixes in query code
3. Check reranker is enabled in config
4. Inspect actual retrieved chunks in evaluation_results.json

## Success Criteria

Migration is successful if:

- ✅ All 170 objects loaded without errors
- ✅ 800-1200 total chunks created
- ✅ < 10% of objects still thin after enrichment
- ✅ Database has 170 documents, 800+ chunks
- ✅ Evaluation success rate > 70%
- ✅ API returns relevant results for test queries

## Next Steps After Migration

1. **Monitor production queries**: Track which queries return good/bad results
2. **Iterate on enrichment**: If certain object types perform poorly, improve signal extraction
3. **Add structured retrieval**: Start implementing MCP tools for structured queries
4. **Update documentation**: Document the new knowledge base structure for users

## Questions?

Review:
- `README.md` - Full technical documentation
- `migration_report.csv` - Object-level statistics
- `evaluation_results.json` - Query-level results
- Enrichment assessment reports in `../scapy/htw_scrape/outputs/objects/`
