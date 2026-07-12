#!/usr/bin/env python3
"""
HANS Content Database Builder

Ingests web JSON data and Excel Q&A pairs into PostgreSQL with pgvector embeddings.
Replaces FAISS/pickle-based storage with database-backed retrieval system.
"""

import argparse
import json
import logging
import hashlib
import uuid
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import pandas as pd
import psycopg
import numpy as np

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from hansdb.conn import load_config, get_db_connection
from hansdb.embeddings import embed_and_normalize, embed_passages, get_embedding_model

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ContentIngester:
    """Handles ingestion of web and Excel content into the database"""
    
    def __init__(self, config: dict, force: bool = False, dry_run: bool = False):
        self.config = config
        self.force = force
        self.dry_run = dry_run
        self.stats = {
            'documents_processed': 0,
            'documents_skipped': 0,
            'web_chunks_created': 0,
            'web_chunks_skipped': 0,
            'qa_pairs_created': 0,
            'qa_pairs_skipped': 0,
            'short_texts_skipped': 0
        }
        
        # Initialize embedding model
        self.embedding_model_name = config['model']['embedding_model']
        get_embedding_model(self.embedding_model_name)
    
    def normalize_text(self, text: str) -> str:
        """Normalize text for consistent processing"""
        return text.strip().replace('\n', ' ').replace('\r', ' ')
    
    def chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[Tuple[int, int, str]]:
        """
        Chunk text into overlapping segments
        
        Returns:
            List of (start_char, end_char, chunk_text) tuples
        """
        if len(text) <= chunk_size:
            return [(0, len(text), text)]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            if end >= len(text):
                end = len(text)
            
            chunk_text = text[start:end]
            chunks.append((start, end, chunk_text))
            
            if end >= len(text):
                break
                
            start += chunk_size - overlap
        
        return chunks
    
    def sha256_hash(*parts: str) -> str:
        """Generate SHA256 hash from multiple string parts"""
        content = ''.join(parts)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def upsert_document(self, conn: psycopg.Connection, doc_data: dict) -> uuid.UUID:
        """Upsert document record and return document ID"""
        doc_id = uuid.uuid4()
        
        # Create document hash for deduplication
        hash_content = f"{doc_data.get('title', '')}{doc_data.get('url', '')}{doc_data.get('source_file', '')}"
        doc_hash = hashlib.sha256(hash_content.encode('utf-8')).hexdigest()
        
        if not self.dry_run:
            with conn.cursor() as cur:
                # Check if document already exists
                if not self.force:
                    cur.execute("SELECT id FROM documents WHERE doc_hash = %s", (doc_hash,))
                    existing = cur.fetchone()
                    if existing:
                        return existing[0]
                
                # Upsert document
                cur.execute("""
                    INSERT INTO documents (id, source_type, title, url, source_file, contacts, links, doc_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (doc_hash) DO UPDATE SET
                        title = EXCLUDED.title,
                        url = EXCLUDED.url,
                        source_file = EXCLUDED.source_file,
                        contacts = EXCLUDED.contacts,
                        links = EXCLUDED.links,
                        updated_at = now()
                    RETURNING id
                """, (
                    doc_id,
                    doc_data['source_type'],
                    doc_data.get('title'),
                    doc_data.get('url'),
                    doc_data.get('source_file'),
                    json.dumps(doc_data.get('contacts', [])),
                    json.dumps(doc_data.get('links', [])),
                    doc_hash
                ))
                
                result = cur.fetchone()
                return result[0] if result else doc_id
        
        return doc_id
    
    def upsert_web_chunk(self, conn: psycopg.Connection, chunk_data: dict) -> Optional[uuid.UUID]:
        """Upsert web chunk with embedding"""
        chunk_id = uuid.uuid4()
        
        # Create content hash for deduplication
        hash_content = f"{chunk_data['text']}{chunk_data.get('url', '')}"
        content_hash = hashlib.sha256(hash_content.encode('utf-8')).hexdigest()
        
        if not self.dry_run:
            with conn.cursor() as cur:
                # Check if chunk already exists
                if not self.force:
                    cur.execute("SELECT id FROM web_chunks WHERE content_hash = %s", (content_hash,))
                    existing = cur.fetchone()
                    if existing:
                        return None  # Skip existing
                
                # Generate embedding (use passage prefix for E5 models)
                embeddings = embed_passages([chunk_data['text']], self.embedding_model_name)
                embedding_vector = embeddings[0].tolist()
                
                # Upsert chunk
                cur.execute("""
                    INSERT INTO web_chunks (
                        id, document_id, chunk_index, start_char, end_char, text,
                        contacts, links, embedding, embedding_model, content_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (content_hash) DO UPDATE SET
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        updated_at = now()
                    RETURNING id
                """, (
                    chunk_id,
                    chunk_data['document_id'],
                    chunk_data['chunk_index'],
                    chunk_data['start_char'],
                    chunk_data['end_char'],
                    chunk_data['text'],
                    json.dumps(chunk_data.get('contacts', [])),
                    json.dumps(chunk_data.get('links', [])),
                    embedding_vector,
                    self.embedding_model_name,
                    content_hash
                ))
                
                return chunk_id
        
        return chunk_id
    
    def upsert_qa_pair(self, conn: psycopg.Connection, qa_data: dict) -> Optional[uuid.UUID]:
        """Upsert Q&A pair with question embedding"""
        qa_id = uuid.uuid4()
        
        # Create content hash for deduplication
        hash_content = f"{qa_data['question']}{qa_data['answer']}"
        content_hash = hashlib.sha256(hash_content.encode('utf-8')).hexdigest()
        
        if not self.dry_run:
            with conn.cursor() as cur:
                # Check if Q&A already exists
                if not self.force:
                    cur.execute("SELECT id FROM qa_pairs WHERE content_hash = %s", (content_hash,))
                    existing = cur.fetchone()
                    if existing:
                        return None  # Skip existing
                
                # Generate question embedding (use passage prefix for E5 models)
                embeddings = embed_passages([qa_data['question']], self.embedding_model_name)
                embedding_vector = embeddings[0].tolist()
                
                # Upsert Q&A pair
                cur.execute("""
                    INSERT INTO qa_pairs (
                        id, question, answer, tags, row_number, source_file,
                        question_embedding, embedding_model, content_hash
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (content_hash) DO UPDATE SET
                        question = EXCLUDED.question,
                        answer = EXCLUDED.answer,
                        question_embedding = EXCLUDED.question_embedding,
                        updated_at = now()
                    RETURNING id
                """, (
                    qa_id,
                    qa_data['question'],
                    qa_data['answer'],
                    json.dumps(qa_data.get('tags', [])),
                    qa_data.get('row_number'),
                    qa_data.get('source_file'),
                    embedding_vector,
                    self.embedding_model_name,
                    content_hash
                ))
                
                return qa_id
        
        return qa_id
    
    def ingest_web_json_files(self, conn: psycopg.Connection, json_dir: Path) -> None:
        """Process all JSON files in the web data directory"""
        logger.info(f"Processing web JSON files from: {json_dir}")
        
        json_files = list(json_dir.glob("*.json"))
        if not json_files:
            logger.warning(f"No JSON files found in {json_dir}")
            return
        
        chunk_config = self.config['ingestion']
        min_chars = chunk_config['min_chars']
        chunk_chars = chunk_config['chunk_chars']
        chunk_overlap = chunk_config['chunk_overlap']
        skip_short = chunk_config['skip_short']
        
        for json_file in json_files:
            logger.info(f"Processing {json_file.name}")
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if not isinstance(data, list):
                    logger.warning(f"Expected list in {json_file.name}, got {type(data)}")
                    continue
                
                for item in data:
                    # Extract content
                    content = item.get('main_content') or item.get('content', '')
                    if not content:
                        logger.warning(f"No content found in item: {item.get('url', 'unknown')}")
                        continue
                    
                    normalized_content = self.normalize_text(content)
                    
                    # Skip short content if configured
                    if skip_short and len(normalized_content) < min_chars:
                        self.stats['short_texts_skipped'] += 1
                        continue
                    
                    # Create document
                    doc_data = {
                        'source_type': 'web',
                        'title': item.get('title'),
                        'url': item.get('url'),
                        'source_file': json_file.name,
                        'contacts': item.get('contacts', []),
                        'links': item.get('links', [])
                    }
                    
                    doc_id = self.upsert_document(conn, doc_data)
                    self.stats['documents_processed'] += 1
                    
                    # Chunk the content
                    chunks = self.chunk_text(normalized_content, chunk_chars, chunk_overlap)
                    
                    for chunk_idx, (start_char, end_char, chunk_text) in enumerate(chunks):
                        chunk_data = {
                            'document_id': doc_id,
                            'chunk_index': chunk_idx,
                            'start_char': start_char,
                            'end_char': end_char,
                            'text': chunk_text,
                            'contacts': item.get('contacts', []),
                            'links': item.get('links', []),
                            'url': item.get('url')
                        }
                        
                        result = self.upsert_web_chunk(conn, chunk_data)
                        if result:
                            self.stats['web_chunks_created'] += 1
                        else:
                            self.stats['web_chunks_skipped'] += 1
            
            except Exception as e:
                logger.error(f"Error processing {json_file.name}: {e}")
                continue
    
    def ingest_excel_qa(self, conn: psycopg.Connection, excel_path: Path) -> None:
        """Process Excel Q&A data"""
        logger.info(f"Processing Excel Q&A from: {excel_path}")
        
        try:
            # Try different sheet names
            sheet_names = ['Sheet1', 'QA', 'Data', None]  # None means first sheet
            df = None
            
            for sheet_name in sheet_names:
                try:
                    df = pd.read_excel(excel_path, sheet_name=sheet_name)
                    logger.info(f"Loaded Excel sheet: {sheet_name or 'first sheet'}")
                    break
                except Exception:
                    continue
            
            if df is None:
                logger.error(f"Could not read Excel file: {excel_path}")
                return
            
            # Look for question and answer columns (case insensitive)
            question_col = None
            answer_col = None
            
            for col in df.columns:
                col_lower = str(col).lower()
                if 'question' in col_lower or 'frage' in col_lower:
                    question_col = col
                elif 'answer' in col_lower or 'antwort' in col_lower:
                    answer_col = col
            
            if not question_col or not answer_col:
                logger.error(f"Could not find question/answer columns in {excel_path}")
                logger.info(f"Available columns: {list(df.columns)}")
                return
            
            logger.info(f"Using columns - Question: {question_col}, Answer: {answer_col}")
            
            for idx, row in df.iterrows():
                question = str(row[question_col]).strip()
                answer = str(row[answer_col]).strip()
                
                if not question or not answer or question == 'nan' or answer == 'nan':
                    continue
                
                qa_data = {
                    'question': question,
                    'answer': answer,
                    'tags': [],
                    'row_number': idx + 2,  # Excel row number (accounting for header)
                    'source_file': excel_path.name
                }
                
                result = self.upsert_qa_pair(conn, qa_data)
                if result:
                    self.stats['qa_pairs_created'] += 1
                else:
                    self.stats['qa_pairs_skipped'] += 1
        
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
    
    def run(self, conn: psycopg.Connection, only: Optional[str] = None) -> None:
        """Run the ingestion process"""
        paths = self.config['paths']
        
        if only in [None, 'web']:
            web_json_dir = Path(paths['web_json_dir'])
            if web_json_dir.exists():
                self.ingest_web_json_files(conn, web_json_dir)
            else:
                logger.warning(f"Web JSON directory not found: {web_json_dir}")
        
        if only in [None, 'excel']:
            excel_path = Path(paths['excel_path'])
            if excel_path.exists():
                self.ingest_excel_qa(conn, excel_path)
            else:
                logger.warning(f"Excel file not found: {excel_path}")
        
        if not self.dry_run:
            conn.commit()
        
        self.print_stats()
    
    def print_stats(self):
        """Print ingestion statistics"""
        logger.info("Ingestion completed. Statistics:")
        logger.info(f"  Documents processed: {self.stats['documents_processed']}")
        logger.info(f"  Documents skipped: {self.stats['documents_skipped']}")
        logger.info(f"  Web chunks created: {self.stats['web_chunks_created']}")
        logger.info(f"  Web chunks skipped: {self.stats['web_chunks_skipped']}")
        logger.info(f"  Q&A pairs created: {self.stats['qa_pairs_created']}")
        logger.info(f"  Q&A pairs skipped: {self.stats['qa_pairs_skipped']}")
        logger.info(f"  Short texts skipped: {self.stats['short_texts_skipped']}")

def ensure_database_schema(conn: psycopg.Connection, config: dict) -> None:
    """Ensure database schema is set up correctly"""
    logger.info("Setting up database schema...")
    
    # Read and execute DDL
    ddl_path = Path(__file__).parent.parent / "db" / "ddl.sql"
    
    try:
        with open(ddl_path, 'r') as f:
            ddl_sql = f.read()
        
        with conn.cursor() as cur:
            cur.execute(ddl_sql)
        
        # Update schema version
        schema_version = config['schema_version']
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO meta (key, value) VALUES ('schema_version', %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (str(schema_version),))
        
        conn.commit()
        logger.info("Database schema set up successfully")
    
    except Exception as e:
        logger.error(f"Failed to set up database schema: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Build HANS content database")
    parser.add_argument("--force", action="store_true", 
                       help="Re-embed and rebuild all items")
    parser.add_argument("--dry-run", action="store_true",
                       help="Show changes without writing to database")
    parser.add_argument("--only", choices=["web", "excel"],
                       help="Process only web or excel content")
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config()
        
        # Get database connection
        conn = get_db_connection(config)
        
        # Set up schema
        ensure_database_schema(conn, config)
        
        # Run ingestion
        ingester = ContentIngester(config, force=args.force, dry_run=args.dry_run)
        ingester.run(conn, only=args.only)
        
        conn.close()
        logger.info("Content database build completed successfully")
    
    except Exception as e:
        logger.error(f"Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()