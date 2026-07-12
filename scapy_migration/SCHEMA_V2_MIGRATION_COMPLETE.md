# Schema V2 Migration - Completion Report

## Summary

Successfully created and migrated to new PostgreSQL schema `hans_v2` designed specifically for the 170 curated scapy objects RAG approach.

**Migration Date:** 2026-01-25
**Status:** ✅ COMPLETE

---

## What Was Done

### 1. Created New Schema (schema_v2.sql)

**Schema Design:**
- **Namespace:** `hans_v2` (separate from old schema for rollback safety)
- **Tables Created:**
  - `hans_v2.documents` - Stores curated object metadata
  - `hans_v2.chunks` - Stores text chunks with embeddings

**Table: hans_v2.documents**
- Stores complete metadata from JSON objects
- Fields: object_id, object_type, url, title, page_id, dates, classification info
- Stores `raw_json` (full object) for traceability
- Stores `related_pages` as JSONB
- 170 records loaded

**Table: hans_v2.chunks**
- Stores text chunks with 768-dimensional BGE embeddings
- Fields: document_id (FK), chunk_index, chunk_text, chunk_text_len, enriched, still_thin, embedding
- Uses `vector(768)` type for embeddings
- 930 chunks loaded (avg 5.47 per document)

**Indexes Created:**
- Documents: indexes on object_type, url, object_id
- Chunks: indexes on document_id, enriched, still_thin
- Vector search: IVFFlat index on embedding using cosine distance (lists=100)

### 2. Updated Migration Script (migrate_scapy_to_db.py)

**Changes Made:**
- Modified `store_chunks_in_db()` to insert into hans_v2 tables
- Updated to store full object metadata (not just url/title)
- Store enrichment flags (enriched, still_thin) per chunk
- Modified `clear_existing_vectors()` to truncate only hans_v2 tables
- Added post-insert validation checks
- Old schema tables (documents, web_chunks) left untouched for rollback

**Metadata Stored:**
- Full object JSON in `raw_json` column
- All metadata fields (object_id, object_type, url, title, page_id, dates, classification)
- Related pages as JSONB array
- Enrichment status per document

---

## Migration Results

### Statistics

```
Total objects processed: 170
Objects enriched: 17 (10%)
Objects still thin: 9 (5.3%)
Total chunks created: 930
Average chunks per object: 5.47
Chunks per document range: 1-16
```

### Database Verification

```sql
-- Document count
SELECT COUNT(*) FROM hans_v2.documents;
-- Result: 170 ✓

-- Chunk count
SELECT COUNT(*) FROM hans_v2.chunks;
-- Result: 930 ✓

-- Enrichment statistics
SELECT
    COUNT(*) as total_chunks,
    SUM(CASE WHEN enriched THEN 1 ELSE 0 END) as enriched_count,
    SUM(CASE WHEN still_thin THEN 1 ELSE 0 END) as still_thin_count
FROM hans_v2.chunks;
-- All validation passed ✓
```

### Post-Migration Actions Completed

1. ✅ Ran `ANALYZE hans_v2.chunks` for optimal ivfflat performance
2. ✅ Verified all 170 documents inserted correctly
3. ✅ Verified all 930 chunks inserted correctly
4. ✅ Verified enrichment flags stored correctly
5. ✅ Verified vector embeddings stored (768 dimensions)

---

## Files Created/Modified

### New Files
1. **schema_v2.sql** - Complete schema definition with indexes
2. **migration_report_v2.csv** - Per-object statistics
3. **SCHEMA_V2_MIGRATION_COMPLETE.md** - This document

### Modified Files
1. **migrate_scapy_to_db.py** - Updated to use hans_v2 schema
   - Line 102-120: `clear_existing_vectors()` updated
   - Line 123-251: `store_chunks_in_db()` rewritten
   - Line 352-382: Added post-insert validation

---

## Schema Details

### Table: hans_v2.documents

```sql
CREATE TABLE hans_v2.documents (
    id BIGSERIAL PRIMARY KEY,
    object_id TEXT UNIQUE NOT NULL,
    object_type TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    page_id TEXT,
    last_scraped DATE,
    last_processed TIMESTAMPTZ,
    classification_confidence TEXT,
    classification_notes TEXT,
    related_pages JSONB,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Table: hans_v2.chunks

```sql
CREATE TABLE hans_v2.chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES hans_v2.documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_text_len INT NOT NULL,
    enriched BOOLEAN NOT NULL DEFAULT FALSE,
    still_thin BOOLEAN NOT NULL DEFAULT FALSE,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);
```

### Vector Search Index

```sql
CREATE INDEX idx_chunks_embedding_ivfflat
ON hans_v2.chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

---

## How to Use New Schema

### Query Documents

```sql
-- Find documents by type
SELECT object_id, title, url
FROM hans_v2.documents
WHERE object_type = 'application_process';

-- Get document with all metadata
SELECT object_id, object_type, title, url, classification_notes, related_pages
FROM hans_v2.documents
WHERE object_id = 'accessibility_support-barrier-free-campus';
```

### Query Chunks

```sql
-- Get all chunks for a document
SELECT c.chunk_index, c.chunk_text, c.chunk_text_len, c.enriched, c.still_thin
FROM hans_v2.chunks c
JOIN hans_v2.documents d ON c.document_id = d.id
WHERE d.object_id = 'accessibility_support-barrier-free-campus'
ORDER BY c.chunk_index;

-- Count chunks per document type
SELECT d.object_type, COUNT(*) as chunk_count
FROM hans_v2.chunks c
JOIN hans_v2.documents d ON c.document_id = d.id
GROUP BY d.object_type
ORDER BY chunk_count DESC;
```

### Vector Search (Basic)

```sql
-- Find similar chunks (example with placeholder embedding)
SELECT
    d.object_id,
    d.title,
    d.url,
    c.chunk_text,
    c.embedding <=> '[placeholder_768_dim_vector]'::vector as distance
FROM hans_v2.chunks c
JOIN hans_v2.documents d ON c.document_id = d.id
ORDER BY c.embedding <=> '[placeholder_768_dim_vector]'::vector
LIMIT 10;
```

**Note:** For actual retrieval, use the BGE model to generate query embeddings first.

---

## Next Steps

### Immediate Actions

1. **Update Retrieval Code** (NOT YET DONE)
   - Modify retrieval functions to query `hans_v2.chunks` instead of `web_chunks`
   - Update joins to use `hans_v2.documents` instead of `documents`
   - Update distance operator (use `<=>` for cosine with ivfflat)
   - Remove any E5 prefixes from query embedding code

2. **Update Configuration** (NOT YET DONE)
   - Update retrieval config to point to hans_v2 tables
   - Confirm ivfflat.probes setting (currently 10 in config)

3. **Test End-to-End**
   - Run test queries through retrieval pipeline
   - Verify results match expectations
   - Compare performance vs old schema

### Performance Tuning

1. **Monitor IVFFlat Performance**
   ```sql
   -- Adjust probes for recall vs speed tradeoff
   SET ivfflat.probes = 10;  -- Default
   -- Increase for better recall: SET ivfflat.probes = 20;
   ```

2. **Rebuild Index After Major Changes**
   ```sql
   DROP INDEX IF EXISTS hans_v2.idx_chunks_embedding_ivfflat;
   ANALYZE hans_v2.chunks;
   CREATE INDEX idx_chunks_embedding_ivfflat
   ON hans_v2.chunks
   USING ivfflat (embedding vector_cosine_ops)
   WITH (lists = 100);
   ```

### Future Enhancements

- Consider HNSW index for better recall (requires pgvector 0.5.0+)
- Add full-text search indexes if needed
- Add indexes on other frequently queried fields
- Consider partitioning if dataset grows significantly

---

## Rollback Plan

If needed, rollback is straightforward since old schema is untouched:

1. **Revert retrieval code** to query old tables (documents, web_chunks)
2. **Optional:** Drop v2 schema
   ```sql
   DROP SCHEMA hans_v2 CASCADE;
   ```

Old data is preserved in original tables.

---

## Success Criteria - All Met

✅ Total chunks increased from ~700 to 930
✅ 170 documents loaded correctly
✅ All metadata preserved in raw_json
✅ Enrichment flags stored per chunk
✅ Average chunks 5.47 (within target 4-8 range)
✅ Objects with ≤3 chunks: 12 (7.1%, well below 20% threshold)
✅ Vector embeddings stored (768 dims, BGE)
✅ Indexes created and optimized
✅ Post-insert validation passed
✅ Old schema untouched (rollback safe)

---

## Technical Notes

### Embedding Model
- **Model:** BAAI/bge-base-en-v1.5
- **Dimensions:** 768
- **Normalization:** Yes (normalize_embeddings=True)
- **Prefixes:** None (BGE doesn't use query:/passage: prefixes like E5)

### Chunking Parameters
- **chunk_chars:** 1000 (default)
- **chunk_overlap:** 200
- **min_chars:** 250
- **Guaranteed minimums:**
  - ≥7000 chars → min 10 chunks
  - ≥3500 chars → min 6 chunks
  - ≥1800 chars → min 4 chunks
  - ≥1000 chars → min 3 chunks

### Text Cleaning
- Header prefix removal (HTW Berlin boilerplate)
- Breadcrumb filtering
- Whitespace normalization
- **Critical fix applied:** Don't delete entire single-line content

### Enrichment Strategy
- Thin objects borrow 1200-2000 chars from related pages
- 17 objects enriched (10%)
- 9 still thin after enrichment (5.3%)

---

## Contact & Documentation

- **Migration script:** migrate_scapy_to_db.py
- **Schema file:** schema_v2.sql
- **Report:** migration_report_v2.csv
- **Full docs:** See README.md, IMPLEMENTATION_SUMMARY.md

---

**Migration completed successfully on 2026-01-25.**
**Ready for retrieval code integration.**
