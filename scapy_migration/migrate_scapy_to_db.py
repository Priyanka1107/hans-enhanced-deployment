#!/usr/bin/env python3
"""
Main migration pipeline: Load scapy objects, build enriched embeddings, chunk, embed, and store in PostgreSQL.

Usage:
    python migrate_scapy_to_db.py --objects-dir ../scapy/htw_scrape/outputs/objects \
                                   --report-csv migration_report.csv \
                                   --config ../config.yaml \
                                   --dry-run  # optional: don't write to DB
"""

import argparse
import json
import csv
import logging
import sys
from pathlib import Path
from typing import Dict, List
import yaml
import psycopg
from sentence_transformers import SentenceTransformer
import numpy as np

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from scapy_migration.text_cleaning import clean_full_text
from scapy_migration.embedding_builder import build_embedding_text
from scapy_migration.chunking import chunk_embedding_text
from hansdb.conn import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_all_objects(objects_dir: Path) -> Dict[str, dict]:
    """
    Load all JSON objects from directory.

    Returns:
        Dict mapping object_id -> object
    """
    logger.info(f"Loading objects from {objects_dir}")

    obj_by_id = {}
    json_files = list(objects_dir.glob('*.json'))

    logger.info(f"Found {len(json_files)} JSON files")

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                obj = json.load(f)

            object_id = obj.get('metadata', {}).get('object_id')
            if not object_id:
                logger.warning(f"Skipping {json_file.name}: no object_id")
                continue

            obj_by_id[object_id] = obj

        except Exception as e:
            logger.error(f"Error loading {json_file.name}: {e}")

    logger.info(f"Loaded {len(obj_by_id)} objects")
    return obj_by_id


def generate_migration_report(
    objects_data: List[dict],
    report_path: Path
):
    """
    Generate CSV report of object processing stats.

    Args:
        objects_data: List of dicts with object stats
        report_path: Output CSV path
    """
    logger.info(f"Writing report to {report_path}")

    with open(report_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'object_id',
            'object_type',
            'cleaned_full_text_len',
            'embedding_text_len_before_enrich',
            'embedding_text_len_after_enrich',
            'enriched_true_false',
            'still_thin_true_false',
            'num_chunks'
        ])
        writer.writeheader()
        writer.writerows(objects_data)

    logger.info(f"Report written with {len(objects_data)} rows")


def clear_existing_vectors(conn: psycopg.Connection, dry_run: bool = False):
    """
    Clear existing vectors from scapy objects in hans_v2 schema (migration mode).

    Truncates hans_v2.chunks and hans_v2.documents tables.
    Note: Old schema tables (documents, web_chunks) are left untouched for rollback safety.
    """
    if dry_run:
        logger.info("DRY RUN: Would truncate hans_v2.chunks and hans_v2.documents tables")
        return

    logger.warning("Truncating hans_v2.chunks and hans_v2.documents tables...")

    with conn.cursor() as cur:
        # Truncate in correct order (chunks first due to foreign key)
        cur.execute("TRUNCATE TABLE hans_v2.chunks CASCADE")
        cur.execute("TRUNCATE TABLE hans_v2.documents CASCADE")

    conn.commit()
    logger.info("V2 tables truncated")


def store_chunks_in_db(
    conn: psycopg.Connection,
    all_chunks: List[Dict],
    obj_by_id: Dict[str, dict],
    embedding_model: SentenceTransformer,
    dry_run: bool = False
):
    """
    Embed chunks and store in PostgreSQL using schema hans_v2.

    Args:
        conn: Database connection
        all_chunks: List of chunk dicts with text and metadata
        obj_by_id: Dict mapping object_id -> full object (for metadata)
        embedding_model: BGE model for embedding
        dry_run: If True, skip DB writes
    """
    if not all_chunks:
        logger.warning("No chunks to store")
        return

    logger.info(f"Embedding and storing {len(all_chunks)} chunks...")

    # Group chunks by object_id to create documents
    chunks_by_obj = {}
    for chunk in all_chunks:
        obj_id = chunk['object_id']
        if obj_id not in chunks_by_obj:
            chunks_by_obj[obj_id] = []
        chunks_by_obj[obj_id].append(chunk)

    # Create document records in hans_v2.documents
    doc_id_map = {}  # object_id -> document.id
    if not dry_run:
        with conn.cursor() as cur:
            for obj_id, chunks in chunks_by_obj.items():
                obj = obj_by_id[obj_id]
                metadata = obj.get('metadata', {})

                # Extract metadata fields
                object_type = metadata.get('object_type', 'unknown')
                url = metadata.get('url', '')
                title = metadata.get('title', '')
                page_id = metadata.get('page_id')
                last_scraped = metadata.get('last_scraped')
                last_processed = metadata.get('last_processed')
                classification_confidence = metadata.get('classification_confidence')
                classification_notes = metadata.get('classification_notes')
                related_pages = obj.get('related_pages', [])

                # Insert document and get ID
                cur.execute("""
                    INSERT INTO hans_v2.documents (
                        object_id, object_type, url, title, page_id,
                        last_scraped, last_processed, classification_confidence,
                        classification_notes, related_pages, raw_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    obj_id,
                    object_type,
                    url,
                    title,
                    page_id,
                    last_scraped,
                    last_processed,
                    classification_confidence,
                    classification_notes,
                    json.dumps(related_pages) if related_pages else None,
                    json.dumps(obj)
                ))
                doc_id = cur.fetchone()[0]
                doc_id_map[obj_id] = doc_id

        conn.commit()
        logger.info(f"Created {len(doc_id_map)} document records in hans_v2.documents")

    # Batch embed chunks
    batch_size = 32
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i+batch_size]
        texts = [chunk['text'] for chunk in batch]

        # Embed with BGE (NO e5 prefixes)
        embeddings = embedding_model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        if dry_run:
            logger.info(f"DRY RUN: Would store batch {i//batch_size + 1} ({len(batch)} chunks)")
            continue

        # Store chunks in hans_v2.chunks
        with conn.cursor() as cur:
            for chunk, embedding in zip(batch, embeddings):
                doc_id = doc_id_map[chunk['object_id']]

                # Convert numpy array to list for pgvector
                embedding_list = embedding.tolist()

                cur.execute("""
                    INSERT INTO hans_v2.chunks (
                        document_id, chunk_index, chunk_text, chunk_text_len,
                        enriched, still_thin, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                """, (
                    doc_id,
                    chunk['chunk_index'],
                    chunk['text'],
                    len(chunk['text']),
                    chunk.get('enriched', False),
                    chunk.get('still_thin', False),
                    embedding_list
                ))

        conn.commit()

        if (i // batch_size + 1) % 10 == 0:
            logger.info(f"Stored {i + len(batch)}/{len(all_chunks)} chunks")

    logger.info("All chunks stored successfully in hans_v2.chunks")


def main():
    parser = argparse.ArgumentParser(description='Migrate scapy objects to PostgreSQL')
    parser.add_argument('--objects-dir', required=True, help='Path to scapy objects directory')
    parser.add_argument('--report-csv', default='migration_report.csv', help='Output CSV report path')
    parser.add_argument('--config', default='../config.yaml', help='Config file path')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no DB writes)')
    parser.add_argument('--chunk-chars', type=int, default=1000, help='Target chunk size')
    parser.add_argument('--chunk-overlap', type=int, default=200, help='Chunk overlap')
    parser.add_argument('--min-chars', type=int, default=250, help='Minimum chunk size')

    args = parser.parse_args()

    objects_dir = Path(args.objects_dir)
    if not objects_dir.exists():
        logger.error(f"Objects directory not found: {objects_dir}")
        sys.exit(1)

    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}
        logger.warning(f"Config file not found: {config_path}, using defaults")

    # A) Load all objects
    obj_by_id = load_all_objects(objects_dir)

    if not obj_by_id:
        logger.error("No objects loaded")
        sys.exit(1)

    # B) Build embedding text for each object
    logger.info("Building enriched embedding text for all objects...")

    objects_data = []
    all_chunks = []

    for object_id, obj in obj_by_id.items():
        try:
            # Build embedding text with enrichment
            embedding_text, enrichment_info = build_embedding_text(obj, obj_by_id)

            # C) Chunk the embedding text
            chunks = chunk_embedding_text(
                embedding_text,
                obj,
                chunk_chars=args.chunk_chars,
                chunk_overlap=args.chunk_overlap,
                min_chars=args.min_chars
            )

            all_chunks.extend(chunks)

            # Track stats for report
            objects_data.append({
                'object_id': object_id,
                'object_type': obj.get('metadata', {}).get('object_type', 'unknown'),
                'cleaned_full_text_len': enrichment_info['cleaned_full_text_len'],
                'embedding_text_len_before_enrich': enrichment_info['embedding_text_len_before'],
                'embedding_text_len_after_enrich': enrichment_info['embedding_text_len_after'],
                'enriched_true_false': enrichment_info['enriched'],
                'still_thin_true_false': enrichment_info['still_thin'],
                'num_chunks': len(chunks)
            })

        except Exception as e:
            logger.error(f"Error processing {object_id}: {e}", exc_info=True)

    # H) Generate report
    generate_migration_report(objects_data, Path(args.report_csv))

    # Print summary
    total_chunks = len(all_chunks)
    enriched_count = sum(1 for d in objects_data if d['enriched_true_false'])
    still_thin_count = sum(1 for d in objects_data if d['still_thin_true_false'])

    logger.info("=" * 60)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total objects processed: {len(obj_by_id)}")
    logger.info(f"Objects enriched with related content: {enriched_count}")
    logger.info(f"Objects still thin after enrichment: {still_thin_count}")
    logger.info(f"Total chunks created: {total_chunks}")
    logger.info(f"Average chunks per object: {total_chunks / len(obj_by_id):.1f}")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE: Skipping database operations")
        logger.info(f"Report written to {args.report_csv}")
        return

    # F) Load embedding model (BAAI/bge-base-en-v1.5)
    logger.info("Loading BGE embedding model...")
    embedding_model = SentenceTransformer('BAAI/bge-base-en-v1.5')
    logger.info("Model loaded")

    # Connect to database
    logger.info("Connecting to database...")
    conn = get_db_connection(config)

    try:
        # Clear existing data
        clear_existing_vectors(conn, dry_run=args.dry_run)

        # Store chunks
        store_chunks_in_db(conn, all_chunks, obj_by_id, embedding_model, dry_run=args.dry_run)

        # Post-insert validation
        if not args.dry_run:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM hans_v2.documents")
                doc_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM hans_v2.chunks")
                chunk_count = cur.fetchone()[0]

            logger.info("=" * 60)
            logger.info("POST-INSERT VALIDATION")
            logger.info("=" * 60)
            logger.info(f"Documents in hans_v2.documents: {doc_count}")
            logger.info(f"Chunks in hans_v2.chunks: {chunk_count}")
            logger.info(f"Expected documents: {len(obj_by_id)}")
            logger.info(f"Expected chunks: {total_chunks}")

            if doc_count != len(obj_by_id):
                logger.warning(f"Document count mismatch! Expected {len(obj_by_id)}, got {doc_count}")
            if chunk_count != total_chunks:
                logger.warning(f"Chunk count mismatch! Expected {total_chunks}, got {chunk_count}")

            if doc_count == len(obj_by_id) and chunk_count == total_chunks:
                logger.info("✓ Validation passed!")

        logger.info("=" * 60)
        logger.info("MIGRATION COMPLETE")
        logger.info("=" * 60)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
