"""
Unified retrieval system for HANS database
"""

import psycopg
import logging
from typing import List, Dict, Any, Optional
from collections import OrderedDict
import numpy as np
from .embeddings import embed_single_text, embed_query
from sentence_transformers import CrossEncoder

logger = logging.getLogger(__name__)

# Global reranker model instance (lazy-loaded)
_reranker_model: Optional[CrossEncoder] = None

def get_reranker_model(model_name: str) -> CrossEncoder:
    """
    Get or initialize the cross-encoder reranker model (singleton pattern)

    Args:
        model_name: Name of the cross-encoder model

    Returns:
        Initialized CrossEncoder model
    """
    global _reranker_model

    if _reranker_model is None:
        logger.info(f"Loading reranker model: {model_name}")
        _reranker_model = CrossEncoder(model_name)
        logger.info(f"Reranker model loaded successfully")

    return _reranker_model

def retrieve_top_k(
    conn: psycopg.Connection,
    query_text: str,
    top_k: int = 6,
    model_name: str = "BAAI/bge-base-en-v1.5",
    min_score: float = 0.0,
    reranker_config: Optional[Dict[str, Any]] = None,
    top_k_db: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Unified top-k retrieval that searches both web chunks and Q&A pairs
    with optional cross-encoder reranking

    Args:
        conn: Database connection
        query_text: Query text to search for
        top_k: Final number of top results to return after reranking
        model_name: Embedding model name for query embedding
        min_score: Optional minimum score threshold (max distance for cosine).
                   If > 0.0, filters out results with score > min_score.
                   If 0.0, no filtering is applied.
        reranker_config: Optional reranker configuration dict with keys:
                        'enabled' (bool), 'model_name' (str), 'max_rerank' (int)
        top_k_db: Number of candidates to fetch from DB before reranking.
                  If None, uses top_k.

    Returns:
        List of dictionaries containing search results with metadata
    """
    # Determine how many candidates to fetch from DB
    fetch_k = top_k_db if top_k_db is not None else top_k

    # Generate normalized query embedding (with E5 query prefix if applicable)
    query_embedding = embed_query(query_text, model_name)
    
    # Convert numpy array to list for psycopg
    query_vector = query_embedding.tolist()
    
    # Query web chunks from the active HANS content database
    query = """
    WITH q AS (
        SELECT CAST(%s AS vector) AS v
    )
    SELECT
        'web' AS source_type,
        wc.id::text AS item_id,
        d.title,
        d.url,
        wc.text AS content,
        COALESCE(wc.contacts, d.contacts) AS contacts,
        COALESCE(wc.links, d.links) AS links,
        d.id::text AS object_id,
        d.source_type AS object_type,
        (wc.embedding <=> q.v) AS score
    FROM web_chunks wc
    JOIN documents d
        ON d.id = wc.document_id,
        q
    ORDER BY score ASC
    LIMIT %s;
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (query_vector, fetch_k))
            results = cur.fetchall()

            # Convert results to dictionaries
            retrieval_results = []
            for row in results:
                result = {
                    'source_type': row[0],
                    'item_id': str(row[1]),
                    'title': row[2],
                    'url': row[3],
                    'content': row[4],
                    'contacts': row[5],
                    'links': row[6],
                    'object_id': row[7],
                    'object_type': row[8],
                    'score': float(row[9])
                }
                retrieval_results.append(result)

            # Apply min_score filter if specified
            # Note: score is cosine distance where LOWER is better
            # min_score acts as max_distance threshold
            if min_score > 0.0:
                filtered_results = [r for r in retrieval_results if r['score'] <= min_score]

                # Fallback: if filter removes everything, keep original results
                if len(filtered_results) == 0:
                    logger.warning(
                        f"min_score filter ({min_score}) would remove all results. "
                        f"Keeping all {len(retrieval_results)} unfiltered results."
                    )
                else:
                    logger.info(
                        f"min_score filter ({min_score}) kept {len(filtered_results)}/{len(retrieval_results)} results"
                    )
                    retrieval_results = filtered_results

            # Apply reranking if enabled and we have enough candidates
            if reranker_config and reranker_config.get('enabled', False) and len(retrieval_results) >= 2:
                try:
                    reranker_model_name = reranker_config.get('model_name')
                    max_rerank = reranker_config.get('max_rerank', len(retrieval_results))

                    # Load reranker model
                    reranker = get_reranker_model(reranker_model_name)

                    # Prepare (query, passage) pairs for reranking
                    pairs = [(query_text, result['content']) for result in retrieval_results]

                    # Get reranker scores
                    logger.info(f"Reranking {len(pairs)} candidates with {reranker_model_name}")
                    rerank_scores = reranker.predict(pairs)

                    # Attach rerank scores to results
                    for i, result in enumerate(retrieval_results):
                        result['rerank_score'] = float(rerank_scores[i])

                    # Sort by rerank score (higher is better for cross-encoders)
                    retrieval_results.sort(key=lambda x: x['rerank_score'], reverse=True)

                except Exception as e:
                    logger.warning(f"Reranking failed: {e}. Falling back to vector search ranking.")

            # Merge chunks by document and return top_k
            retrieval_results = _merge_and_cap_documents(retrieval_results, top_k)

            logger.info(f"Retrieved {len(retrieval_results)} results for query")
            return retrieval_results
    
    except psycopg.Error as exc:
        logger.error("Database query failed: %s", exc)

        try:
            conn.rollback()
        except psycopg.Error:
            logger.exception(
                "Could not roll back failed retrieval transaction"
            )

        raise

def _fetch_raw_chunks(
    conn: psycopg.Connection,
    query_text: str,
    fetch_k: int,
    model_name: str
) -> List[Dict[str, Any]]:
    """
    Low-level helper: embed one query and return the top-k raw chunks
    (no merging, no reranking).
    """
    query_embedding = embed_query(query_text, model_name)
    query_vector = query_embedding.tolist()

    sql = """
    WITH q AS (
        SELECT CAST(%s AS vector) AS v
    )
    SELECT
        'web' AS source_type,
        wc.id::text AS item_id,
        d.title,
        d.url,
        wc.text AS content,
        COALESCE(wc.contacts, d.contacts) AS contacts,
        COALESCE(wc.links, d.links) AS links,
        d.id::text AS object_id,
        d.source_type AS object_type,
        (wc.embedding <=> q.v) AS score
    FROM web_chunks wc
    JOIN documents d
        ON d.id = wc.document_id,
        q
    ORDER BY score ASC
    LIMIT %s;
    """

    with conn.cursor() as cur:
        cur.execute(sql, (query_vector, fetch_k))
        rows = cur.fetchall()

    return [
        {
            'source_type': row[0],
            'item_id': str(row[1]),
            'title': row[2],
            'url': row[3],
            'content': row[4],
            'contacts': row[5],
            'links': row[6],
            'object_id': row[7],
            'object_type': row[8],
            'score': float(row[9]),
        }
        for row in rows
    ]


def _merge_and_cap_documents(
    retrieval_results: List[Dict[str, Any]],
    top_k: int,
    max_chunks_per_doc: int = 3
) -> List[Dict[str, Any]]:
    """
    Merge chunks by document, cap at max_chunks_per_doc, return top_k documents.
    Input must already be sorted by relevance (best first).
    """
    merged = OrderedDict()
    for result in retrieval_results:
        doc_key = result.get('object_id') or result.get('item_id')
        if doc_key not in merged:
            merged[doc_key] = dict(result)
            merged[doc_key]['_chunk_contents'] = [result['content']]
        else:
            if len(merged[doc_key]['_chunk_contents']) < max_chunks_per_doc:
                merged[doc_key]['_chunk_contents'].append(result['content'])
            if 'rerank_score' in result and result['rerank_score'] > merged[doc_key].get('rerank_score', float('-inf')):
                merged[doc_key]['rerank_score'] = result['rerank_score']
            if result['score'] < merged[doc_key]['score']:
                merged[doc_key]['score'] = result['score']

    merged_results = []
    for doc_key, result in merged.items():
        chunks = result.pop('_chunk_contents')
        if len(chunks) > 1:
            result['content'] = '\n\n'.join(chunks)
            logger.info(f"Merged {len(chunks)} chunks for document: {doc_key}")
        merged_results.append(result)

    if len(merged_results) < len(retrieval_results):
        logger.info(
            f"Document merge: {len(retrieval_results)} chunks -> {len(merged_results)} unique documents"
        )
    return merged_results[:top_k]


def retrieve_multi_query(
    conn: psycopg.Connection,
    sub_queries: List[str],
    top_k: int = 5,
    model_name: str = "BAAI/bge-base-en-v1.5",
    min_score: float = 0.0,
    reranker_config: Optional[Dict[str, Any]] = None,
    top_k_db: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Run vector search for each sub-query, pool results, deduplicate
    by chunk ID (boosting chunks found by multiple sub-queries),
    then merge by document and return top_k.

    Args:
        conn: Database connection
        sub_queries: List of self-contained sub-queries
        top_k: Final number of documents to return
        model_name: Embedding model name
        min_score: Max cosine distance threshold (0.0 = no filter)
        reranker_config: Optional reranker config (applied after pooling)
        top_k_db: Candidates per sub-query from DB

    Returns:
        List of merged document results
    """
    fetch_k = top_k_db if top_k_db is not None else 30

    logger.info(f"Multi-query retrieval: {len(sub_queries)} sub-queries, "
                f"{fetch_k} candidates each")

    # ---- Pool raw chunks from all sub-queries ----
    # Key: item_id (chunk id), Value: dict with best score + match count
    pool: Dict[str, Dict[str, Any]] = {}

    for i, sq in enumerate(sub_queries):
        logger.info(f"  Sub-query {i+1}/{len(sub_queries)}: {sq[:80]}...")
        try:
            chunks = _fetch_raw_chunks(conn, sq, fetch_k, model_name)
        except psycopg.Error as e:
            logger.error(f"DB query failed for sub-query {i+1}: {e}")
            continue

        for chunk in chunks:
            cid = chunk['item_id']
            if cid not in pool:
                chunk['_match_count'] = 1
                pool[cid] = chunk
            else:
                pool[cid]['_match_count'] += 1
                # Keep the best (lowest) cosine distance across sub-queries
                if chunk['score'] < pool[cid]['score']:
                    pool[cid]['score'] = chunk['score']

    if not pool:
        logger.warning("Multi-query retrieval returned no results")
        return []

    # ---- Apply multi-match boost ----
    # Chunks retrieved by multiple sub-queries get a small score bonus.
    # score is cosine distance (lower = better), so we multiply by a
    # factor < 1 to improve the score.
    MULTI_MATCH_BOOST = 0.05  # 5% improvement per additional match
    for chunk in pool.values():
        match_count = chunk.pop('_match_count')
        if match_count > 1:
            boost_factor = 1.0 - MULTI_MATCH_BOOST * (match_count - 1)
            boost_factor = max(boost_factor, 0.7)  # floor at 30% boost
            original = chunk['score']
            chunk['score'] = chunk['score'] * boost_factor
            logger.info(
                f"Chunk {chunk['item_id']} matched {match_count} sub-queries: "
                f"score {original:.4f} -> {chunk['score']:.4f}"
            )

    # ---- Sort pooled results by (boosted) score ----
    pooled = sorted(pool.values(), key=lambda x: x['score'])

    logger.info(f"Pooled {len(pooled)} unique chunks from {len(sub_queries)} sub-queries")

    # ---- Apply min_score filter ----
    if min_score > 0.0:
        filtered = [r for r in pooled if r['score'] <= min_score]
        if not filtered:
            logger.warning(
                f"min_score filter ({min_score}) would remove all results. Keeping all."
            )
        else:
            logger.info(f"min_score filter kept {len(filtered)}/{len(pooled)} results")
            pooled = filtered

    # ---- Optional reranking on the pooled set ----
    if reranker_config and reranker_config.get('enabled', False) and len(pooled) >= 2:
        try:
            reranker_model_name = reranker_config.get('model_name')
            max_rerank = reranker_config.get('max_rerank', len(pooled))
            reranker = get_reranker_model(reranker_model_name)

            # Rerank using the FIRST sub-query as the reference (closest to
            # original intent) — or we could use the original query passed
            # separately, but sub_queries[0] is a reasonable proxy.
            pairs = [(sub_queries[0], r['content']) for r in pooled[:max_rerank]]
            logger.info(f"Reranking {len(pairs)} pooled candidates")
            scores = reranker.predict(pairs)
            for j, r in enumerate(pooled[:max_rerank]):
                r['rerank_score'] = float(scores[j])
            pooled.sort(key=lambda x: x.get('rerank_score', float('-inf')), reverse=True)
        except Exception as e:
            logger.warning(f"Reranking failed: {e}. Using vector scores.")

    # ---- Merge by document + cap ----
    return _merge_and_cap_documents(pooled, top_k)


def retrieve_web_chunks_only(
    conn: psycopg.Connection,
    query_text: str,
    top_k: int = 6,
    model_name: str = "BAAI/bge-base-en-v1.5"
) -> List[Dict[str, Any]]:
    """
    Retrieve only from web chunks
    
    Args:
        conn: Database connection
        query_text: Query text to search for
        top_k: Number of top results to return
        model_name: Embedding model name for query embedding
    
    Returns:
        List of web chunk search results
    """
    query_embedding = embed_single_text(query_text, model_name)
    query_vector = query_embedding.tolist()
    
    query = """
    SELECT
        wc.id,
        d.title,
        d.url,
        wc.text,
        COALESCE(wc.contacts, d.contacts) AS contacts,
        COALESCE(wc.links, d.links) AS links,
        d.id::text AS object_id,
        d.source_type AS object_type,
        (wc.embedding <=> %s) AS score
    FROM web_chunks wc
    JOIN documents d
        ON d.id = wc.document_id
    ORDER BY wc.embedding <=> %s
    LIMIT %s;
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (query_vector, query_vector, top_k))
            results = cur.fetchall()
            
            retrieval_results = []
            for row in results:
                result = {
                    'source_type': 'web',
                    'item_id': str(row[0]),
                    'title': row[1],
                    'url': row[2],
                    'content': row[3],
                    'contacts': row[4],
                    'links': row[5],
                    'object_id': row[6],
                    'object_type': row[7],
                    'score': float(row[8])
                }
                retrieval_results.append(result)

            return retrieval_results
    
    except psycopg.Error as exc:
        logger.error("Web chunks query failed: %s", exc)

        try:
            conn.rollback()
        except psycopg.Error:
            logger.exception(
                "Could not roll back failed web retrieval transaction"
            )

        raise

def retrieve_qa_pairs_only(
    conn: psycopg.Connection,
    query_text: str,
    top_k: int = 6,
    model_name: str = "BAAI/bge-base-en-v1.5"
) -> List[Dict[str, Any]]:
    """
    Retrieve only from Q&A pairs
    
    Args:
        conn: Database connection
        query_text: Query text to search for
        top_k: Number of top results to return
        model_name: Embedding model name for query embedding
    
    Returns:
        List of Q&A pair search results
    """
    query_embedding = embed_single_text(query_text, model_name)
    query_vector = query_embedding.tolist()
    
    query = """
    SELECT
      qa.id,
      qa.question,
      qa.answer,
      qa.tags,
      qa.source_file,
      (qa.question_embedding <=> %s) AS score
    FROM qa_pairs qa
    ORDER BY qa.question_embedding <=> %s
    LIMIT %s;
    """
    
    try:
        with conn.cursor() as cur:
            cur.execute(query, (query_vector, query_vector, top_k))
            results = cur.fetchall()
            
            retrieval_results = []
            for row in results:
                result = {
                    'source_type': 'excel',
                    'item_id': str(row[0]),
                    'question': row[1],
                    'content': row[2],  # answer as content
                    'tags': row[3],
                    'source_file': row[4],
                    'score': float(row[5])
                }
                retrieval_results.append(result)
            
            return retrieval_results
    
    except psycopg.Error as e:
        logger.error(f"Q&A pairs query failed: {e}")
        raise

def get_retrieval_stats(
    conn: psycopg.Connection,
) -> Dict[str, int]:
    """
    Return row counts from the active schema-v1 HANS tables.

    The deployment database currently uses:
    - public.documents
    - public.web_chunks
    - public.qa_pairs
    """
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents")
            document_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM web_chunks")
            web_chunk_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM qa_pairs")
            qa_pair_count = cur.fetchone()[0]

        return {
            "documents": document_count,
            "web_chunks": web_chunk_count,
            "qa_pairs": qa_pair_count,
        }

    except psycopg.Error as exc:
        logger.error("Stats query failed: %s", exc)

        # A failed PostgreSQL statement leaves the transaction aborted.
        # Roll back so later validation queries can still run.
        try:
            conn.rollback()
        except psycopg.Error:
            logger.exception(
                "Could not roll back failed statistics transaction"
            )

        raise