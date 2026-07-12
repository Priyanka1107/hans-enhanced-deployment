#!/usr/bin/env python3
"""
Minimal evaluation script for retrieval quality.

Tests whether correct object_ids appear in top-10 results for test queries.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict
import yaml
import psycopg
from sentence_transformers import SentenceTransformer
import numpy as np

sys.path.append(str(Path(__file__).parent.parent))

from hansdb.conn import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_test_queries(queries_file: Path) -> List[Dict]:
    """Load test queries from JSON file."""
    with open(queries_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def retrieve_chunks(
    conn: psycopg.Connection,
    query_embedding: np.ndarray,
    top_k: int = 30
) -> List[Dict]:
    """
    Retrieve top-k chunks using vector similarity.

    Returns list of dicts with chunk_text, object_id, object_type, url, similarity
    """
    embedding_list = query_embedding.tolist()

    with conn.cursor() as cur:
        # Join web_chunks with documents to get metadata
        cur.execute("""
            SELECT
                wc.chunk_text,
                d.url,
                d.title,
                1 - (wc.embedding <=> %s::vector) AS similarity,
                wc.chunk_id
            FROM web_chunks wc
            JOIN documents d ON wc.doc_id = d.doc_id
            ORDER BY wc.embedding <=> %s::vector
            LIMIT %s
        """, (embedding_list, embedding_list, top_k))

        results = []
        for row in cur.fetchall():
            chunk_text, url, title, similarity, chunk_id = row

            # Extract object_id from URL or title (best effort)
            # In reality, we should store object_id in documents table
            # For now, use title or URL as proxy
            object_id = extract_object_id_from_url(url) or title

            results.append({
                'chunk_text': chunk_text,
                'url': url,
                'title': title,
                'similarity': float(similarity),
                'chunk_id': chunk_id,
                'object_id': object_id
            })

        return results


def extract_object_id_from_url(url: str) -> str:
    """
    Extract object_id from URL (best effort).

    Example:
    https://www.htw-berlin.de/en/studies/applications/enrolment/
    -> application_process-enrolment
    """
    if not url:
        return "unknown"

    # Get path component
    from urllib.parse import urlparse
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    # Split and clean
    parts = [p for p in path.split('/') if p and p != 'en' and p != 'de']

    if not parts:
        return "unknown"

    # Simplified heuristic: use last 1-2 path components
    if len(parts) >= 2:
        return f"{parts[-2]}-{parts[-1]}"
    else:
        return parts[-1]


def rerank_chunks(
    chunks: List[Dict],
    query: str,
    reranker_model,
    top_n: int = 10
) -> List[Dict]:
    """
    Rerank chunks using cross-encoder.

    Args:
        chunks: List of chunk dicts
        query: Original query string
        reranker_model: Cross-encoder model
        top_n: Number of results to keep

    Returns:
        Top-n reranked chunks
    """
    if not chunks:
        return []

    # Prepare pairs for cross-encoder
    pairs = [(query, chunk['chunk_text']) for chunk in chunks]

    # Get scores
    scores = reranker_model.predict(pairs)

    # Attach scores and sort
    for chunk, score in zip(chunks, scores):
        chunk['rerank_score'] = float(score)

    # Sort by rerank score
    chunks_sorted = sorted(chunks, key=lambda x: x['rerank_score'], reverse=True)

    return chunks_sorted[:top_n]


def evaluate_query(
    query_obj: Dict,
    conn: psycopg.Connection,
    embedding_model: SentenceTransformer,
    reranker_model,
    top_k_retrieve: int = 30,
    top_n_rerank: int = 10
) -> Dict:
    """
    Evaluate single query.

    Returns:
        Dict with results and whether expected types were found
    """
    query = query_obj['query']
    expected_types = query_obj.get('expected_object_types', [])

    # Embed query (NO e5 prefix for BGE)
    query_embedding = embedding_model.encode(
        query,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    # Retrieve candidates
    candidates = retrieve_chunks(conn, query_embedding, top_k=top_k_retrieve)

    # Rerank
    reranked = rerank_chunks(candidates, query, reranker_model, top_n=top_n_rerank)

    # Extract object types from top results
    found_types = set()
    found_objects = set()

    for chunk in reranked:
        # Infer object type from URL/title (best effort)
        # In production, store object_type in DB
        url = chunk['url']
        if 'application' in url or 'enrolment' in url:
            found_types.add('application_process')
        if 'fee' in url or 'funding' in url or 'semester-fee' in url:
            found_types.add('fees_funding_rule')
        if 'language' in url or 'proof' in url or 'dsh' in url or 'english' in url:
            found_types.add('language_proof_rule')
        if 'degree' in url or 'programme' in url or 'bachelor' in url or 'master' in url:
            found_types.add('degree_program')
        if 'support' in url or 'accessibility' in url or 'disability' in url:
            found_types.add('accessibility_support')
        if 'family' in url or 'children' in url:
            found_types.add('family_support')

        found_objects.add(chunk['object_id'])

    # Check if any expected type was found
    match = bool(found_types.intersection(expected_types)) if expected_types else True

    return {
        'query': query,
        'expected_types': expected_types,
        'found_types': list(found_types),
        'found_objects': list(found_objects)[:5],  # Top 5
        'match': match,
        'top_result': reranked[0] if reranked else None
    }


def main():
    parser = argparse.ArgumentParser(description='Evaluate retrieval quality')
    parser.add_argument('--queries', default='test_queries.json', help='Test queries JSON file')
    parser.add_argument('--config', default='../config.yaml', help='Config file')
    parser.add_argument('--top-k', type=int, default=30, help='Candidates to retrieve')
    parser.add_argument('--top-n', type=int, default=10, help='Results after reranking')
    parser.add_argument('--output', default='evaluation_results.json', help='Output results JSON')

    args = parser.parse_args()

    # Load queries
    queries_file = Path(args.queries)
    if not queries_file.exists():
        logger.error(f"Queries file not found: {queries_file}")
        sys.exit(1)

    test_queries = load_test_queries(queries_file)
    logger.info(f"Loaded {len(test_queries)} test queries")

    # Load config
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    # Load models
    logger.info("Loading embedding model (BGE)...")
    embedding_model = SentenceTransformer('BAAI/bge-base-en-v1.5')

    logger.info("Loading reranker model...")
    from sentence_transformers import CrossEncoder
    reranker_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

    # Connect to DB
    logger.info("Connecting to database...")
    conn = get_db_connection(config)

    try:
        # Evaluate each query
        results = []
        matches = 0

        for i, query_obj in enumerate(test_queries, 1):
            logger.info(f"Evaluating query {i}/{len(test_queries)}: {query_obj['query'][:60]}...")

            result = evaluate_query(
                query_obj,
                conn,
                embedding_model,
                reranker_model,
                top_k_retrieve=args.top_k,
                top_n_rerank=args.top_n
            )

            results.append(result)

            if result['match']:
                matches += 1

            # Print result
            logger.info(f"  Expected types: {result['expected_types']}")
            logger.info(f"  Found types: {result['found_types']}")
            logger.info(f"  Match: {result['match']}")
            logger.info("")

        # Summary
        logger.info("=" * 60)
        logger.info("EVALUATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total queries: {len(test_queries)}")
        logger.info(f"Successful matches: {matches}")
        logger.info(f"Success rate: {matches / len(test_queries) * 100:.1f}%")
        logger.info("=" * 60)

        # Save results
        output_path = Path(args.output)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                'summary': {
                    'total_queries': len(test_queries),
                    'matches': matches,
                    'success_rate': matches / len(test_queries)
                },
                'results': results
            }, f, indent=2)

        logger.info(f"Results saved to {output_path}")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
