# ⚡ Quick Start Guide - 5 Minutes to Migration

## Prerequisites Check (30 seconds)

```bash
# Are you in the right directory?
pwd
# Should show: /Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy/scapy_migration

# Do you have the objects?
ls ../scapy/htw_scrape/outputs/objects/*.json | wc -l
# Should show: 170

# Is PostgreSQL running?
docker ps | grep postgres
# Should show container on port 5433
```

## Installation (1 minute)

```bash
# Install Python dependencies
pip3 install -r requirements.txt
```

## Step 1: Verify Setup (2 minutes)

```bash
python3 verify_setup.py
```

**Expected output:**
```
============================================================
HANS Scapy Migration - Setup Verification
============================================================
Checking Python version... ✓ 3.x.x
...
============================================================
SUMMARY
============================================================
✓ PASS: Python version
✓ PASS: Python packages
✓ PASS: Scapy objects
✓ PASS: Config file
✓ PASS: Database
✓ PASS: Models
============================================================

✓ All checks passed! Ready to run migration.
```

**If any checks fail**, see MIGRATION_GUIDE.md troubleshooting section.

## Step 2: Dry Run (30 seconds)

```bash
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --report-csv migration_report.csv \
    --config ../config.yaml \
    --dry-run
```

**Expected output:**
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
INFO - DRY RUN MODE: Skipping database operations
```

**Review the report:**
```bash
# Check thin objects
grep "True" migration_report.csv | grep "still_thin" | wc -l
# Should be < 20

# Check average chunks
awk -F',' '{sum+=$8; count++} END {print sum/count}' migration_report.csv
# Should be 4-8
```

## Step 3: Run Migration (2 minutes)

⚠️ **This will delete existing data!** Backup first:

```bash
# Backup database
pg_dump -h localhost -p 5433 -U hansuser hansdb > backup_$(date +%Y%m%d).sql

# Run migration
python3 migrate_scapy_to_db.py \
    --objects-dir ../scapy/htw_scrape/outputs/objects \
    --report-csv migration_report.csv \
    --config ../config.yaml
```

**Expected output:**
```
INFO - Loading BGE embedding model...
INFO - Model loaded
INFO - Connecting to database...
INFO - Truncating web_chunks and documents tables...
INFO - Embedding and storing chunks...
INFO - Created 170 document records
INFO - Stored 32/1000 chunks
INFO - Stored 64/1000 chunks
...
INFO - All chunks stored successfully
============================================================
MIGRATION COMPLETE
============================================================
```

## Step 4: Verify Migration (30 seconds)

```bash
# Check database
psql -h localhost -p 5433 -U hansuser -d hansdb -c "
SELECT
  (SELECT COUNT(*) FROM documents) as num_docs,
  (SELECT COUNT(*) FROM web_chunks) as num_chunks;
"
```

**Expected:**
```
 num_docs | num_chunks
----------+------------
      170 |        ~1000
```

## Step 5: Test Retrieval (1 minute)

```bash
python3 evaluate_retrieval.py \
    --queries test_queries.json \
    --config ../config.yaml \
    --output evaluation_results.json
```

**Expected output:**
```
INFO - Loaded 25 test queries
...
============================================================
EVALUATION SUMMARY
============================================================
Total queries: 25
Successful matches: 18-21
Success rate: 70-85%
============================================================
```

**Success rate > 70% = Migration successful! ✅**

## Done! 🎉

Your migration is complete. The new knowledge base is now live in PostgreSQL.

### What Changed

- ✅ Switched from E5 to BGE embeddings
- ✅ Removed all "query:" and "passage:" prefixes
- ✅ 170 curated objects → 800-1200 clean chunks
- ✅ Thin objects enriched with related content
- ✅ Type-specific signals extracted

### Next Steps

1. **Update your retrieval code** to remove e5 prefixes:
   ```python
   # Remove this:
   query_embedding = embed_query(f"query: {user_query}")

   # Use this:
   query_embedding = embed_query(user_query)
   ```

2. **Test the API** with real queries:
   ```bash
   cd ..
   python3 htw_assistant_api.py

   # In another terminal:
   curl -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"q": "What is the semester fee?", "max_sources": 10}'
   ```

3. **Monitor performance** and iterate on enrichment if needed

## Troubleshooting

### "No objects loaded"
```bash
ls -la ../scapy/htw_scrape/outputs/objects/*.json
# Check path is correct
```

### "Database connection failed"
```bash
docker ps | grep postgres
# Check PostgreSQL is running

cat ../.env.local | grep DATABASE_URL
# Check credentials are set
```

### Low success rate (< 60%)
```bash
# Check chunk sizes
awk -F',' '{print $8}' migration_report.csv | sort -n | head -20

# Re-run with larger chunks
python3 migrate_scapy_to_db.py --chunk-chars 1200 ...
```

## Need Help?

- **Technical details**: See [README.md](README.md)
- **Step-by-step guide**: See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Implementation notes**: See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)

## Rollback

If something goes wrong:

```bash
# Restore backup
psql -h localhost -p 5433 -U hansuser -d hansdb < backup_YYYYMMDD.sql

# Revert config changes
git checkout ../config.yaml
```

---

**Total time: 5-7 minutes including verification ⚡**
