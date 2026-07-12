-- PostgreSQL schema for HANS database with pgvector support
-- Migrating from FAISS/pickle/Excel to database-backed RAG

CREATE EXTENSION IF NOT EXISTS vector;

-- Meta table for schema versioning
CREATE TABLE IF NOT EXISTS meta (
  key text PRIMARY KEY,
  value text NOT NULL
);
INSERT INTO meta (key, value) VALUES ('schema_version','1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Documents table (web pages and excel sources)
CREATE TABLE IF NOT EXISTS documents (
  id UUID PRIMARY KEY,
  source_type TEXT CHECK (source_type IN ('web','excel')) NOT NULL,
  title TEXT,
  url TEXT,
  source_file TEXT,
  contacts JSONB,
  links JSONB,
  doc_hash TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Web chunks table
CREATE TABLE IF NOT EXISTS web_chunks (
  id UUID PRIMARY KEY,
  document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL,
  start_char INT,
  end_char INT,
  text TEXT NOT NULL,
  contacts JSONB,
  links JSONB,
  embedding VECTOR(768) NOT NULL,
  embedding_model TEXT NOT NULL,
  content_hash TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);

-- Excel Q&A pairs table
CREATE TABLE IF NOT EXISTS qa_pairs (
  id UUID PRIMARY KEY,
  question TEXT NOT NULL,
  answer TEXT NOT NULL,
  tags JSONB,
  row_number INT,
  source_file TEXT,
  question_embedding VECTOR(768) NOT NULL,
  embedding_model TEXT NOT NULL,
  content_hash TEXT UNIQUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Vector indexes (IVFFLAT with cosine distance)
CREATE INDEX IF NOT EXISTS idx_web_chunks_emb_ivf
  ON web_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists=100);

CREATE INDEX IF NOT EXISTS idx_qa_pairs_qemb_ivf
  ON qa_pairs USING ivfflat (question_embedding vector_cosine_ops) WITH (lists=100);

-- Additional indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_doc_hash ON documents(doc_hash);
CREATE INDEX IF NOT EXISTS idx_web_chunks_content_hash ON web_chunks(content_hash);
CREATE INDEX IF NOT EXISTS idx_qa_pairs_content_hash ON qa_pairs(content_hash);