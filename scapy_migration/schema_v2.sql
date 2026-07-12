-- HANS RAG Schema V2 - Scapy Curated Objects
-- Designed for 170 curated JSON objects with embedding-time enrichment
-- Compatible with BAAI/bge-base-en-v1.5 (768-dimensional embeddings)

-- Enable pgvector extension if not already enabled
CREATE EXTENSION IF NOT EXISTS vector;

-- Create new schema namespace
CREATE SCHEMA IF NOT EXISTS hans_v2;

-- ====================
-- Table 1: Documents
-- ====================
-- Stores metadata for each curated scapy object
CREATE TABLE IF NOT EXISTS hans_v2.documents (
    id BIGSERIAL PRIMARY KEY,
    object_id TEXT UNIQUE NOT NULL,           -- metadata.object_id (e.g., "accessibility_support-barrier-free-campus")
    object_type TEXT NOT NULL,                -- metadata.object_type (e.g., "accessibility_support")
    url TEXT NOT NULL,                        -- metadata.url
    title TEXT,                               -- metadata.title
    page_id TEXT,                             -- metadata.page_id
    last_scraped DATE,                        -- metadata.last_scraped
    last_processed TIMESTAMPTZ,               -- metadata.last_processed
    classification_confidence TEXT,           -- metadata.classification_confidence
    classification_notes TEXT,                -- metadata.classification_notes
    related_pages JSONB,                      -- related_pages array as JSONB
    raw_json JSONB NOT NULL,                  -- full object JSON for traceability
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for documents table
CREATE INDEX IF NOT EXISTS idx_documents_object_type ON hans_v2.documents(object_type);
CREATE INDEX IF NOT EXISTS idx_documents_url ON hans_v2.documents(url);
CREATE INDEX IF NOT EXISTS idx_documents_object_id ON hans_v2.documents(object_id);

-- ====================
-- Table 2: Chunks
-- ====================
-- Stores text chunks with embeddings for vector search
CREATE TABLE IF NOT EXISTS hans_v2.chunks (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES hans_v2.documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,                 -- Sequential index within document
    chunk_text TEXT NOT NULL,                 -- The actual chunk content
    chunk_text_len INT NOT NULL,              -- Length in characters
    enriched BOOLEAN NOT NULL DEFAULT FALSE,  -- Was this document enriched with related content?
    still_thin BOOLEAN NOT NULL DEFAULT FALSE,-- Is this still thin after enrichment?
    embedding vector(768) NOT NULL,           -- BGE embedding (768 dimensions)
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);

-- Indexes for chunks table
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON hans_v2.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_enriched ON hans_v2.chunks(enriched);
CREATE INDEX IF NOT EXISTS idx_chunks_still_thin ON hans_v2.chunks(still_thin);

-- ====================
-- Vector Search Index
-- ====================
-- IVFFlat index for approximate nearest neighbor search
-- Note: This index should be created AFTER bulk insert for best performance
-- Run ANALYZE hans_v2.chunks; after inserting data and before creating this index

-- For cosine distance (recommended for BGE embeddings without normalization)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat
ON hans_v2.chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Alternative: For inner product (if embeddings are normalized)
-- CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat_ip
-- ON hans_v2.chunks
-- USING ivfflat (embedding vector_ip_ops)
-- WITH (lists = 100);

-- ====================
-- Performance Notes
-- ====================
-- 1. After bulk insert, run: ANALYZE hans_v2.chunks;
-- 2. For better ivfflat performance, set: SET ivfflat.probes = 10; (or higher)
-- 3. Lists parameter (100) is suitable for ~1000 chunks. Adjust if needed:
--    - General rule: lists = rows / 1000
--    - For 930 chunks: 100 lists is appropriate
-- 4. Drop and recreate ivfflat index after major data changes

-- ====================
-- Verification Queries
-- ====================
-- Check document count:
-- SELECT COUNT(*) as total_documents FROM hans_v2.documents;

-- Check chunk count:
-- SELECT COUNT(*) as total_chunks FROM hans_v2.chunks;

-- Check enrichment statistics:
-- SELECT
--     COUNT(*) as total,
--     SUM(CASE WHEN enriched THEN 1 ELSE 0 END) as enriched_count,
--     SUM(CASE WHEN still_thin THEN 1 ELSE 0 END) as still_thin_count
-- FROM hans_v2.chunks;

-- Average chunks per document:
-- SELECT
--     AVG(chunk_count) as avg_chunks_per_doc,
--     MIN(chunk_count) as min_chunks,
--     MAX(chunk_count) as max_chunks
-- FROM (
--     SELECT document_id, COUNT(*) as chunk_count
--     FROM hans_v2.chunks
--     GROUP BY document_id
-- ) counts;

-- ====================
-- Migration Notes
-- ====================
-- This schema is designed for:
-- - 170 curated JSON objects from scapy
-- - ~800-1000 chunks with guaranteed minimums
-- - BAAI/bge-base-en-v1.5 embeddings (768 dims, no prefixes)
-- - Embedding-time enrichment (17 objects expected to be enriched)
-- - Target: <10% still_thin after enrichment

-- To use this schema:
-- 1. Run this SQL file: psql -h localhost -p 5433 -U postgres -d hans -f schema_v2.sql
-- 2. Run migration: python3 migrate_scapy_to_db.py --objects-dir ../scapy/htw_scrape/outputs/objects
-- 3. Verify counts match expectations (170 docs, ~930 chunks)
-- 4. Run ANALYZE hans_v2.chunks; for optimal vector search
