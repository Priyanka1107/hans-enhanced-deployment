from __future__ import annotations

import logging
from typing import Any, Dict, List

import psycopg

from app.settings import settings
from hansdb.retrieval import retrieve_top_k


logger = logging.getLogger(__name__)


def normalize_baseline_document(
    document: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": str(
            document.get("item_id")
            or document.get("id")
            or ""
        ),
        "title": document.get("title", "") or "",
        "source_url": document.get("url", "") or "",
        "url": document.get("url", "") or "",
        "content": document.get("content", "") or "",
        "chunk_text": document.get("content", "") or "",
        "object_id": document.get("object_id", "") or "",
        "object_type": document.get("object_type", "") or "",
        "score": float(document.get("score", 0.0) or 0.0),
        "rerank_score": document.get("rerank_score"),
        "last_updated": document.get("last_updated", "") or "",
        "is_canonical": bool(
            document.get("is_canonical", False)
        ),
        "priority": int(document.get("priority", 0) or 0),
        "category": (
            document.get("category")
            or document.get("object_type")
            or "general"
        ),
    }


def retrieve_for_topic(
    *,
    connection: psycopg.Connection,
    query: str,
    top_k: int | None = None,
) -> List[Dict[str, Any]]:
    final_top_k = top_k or settings.retrieval_top_k_per_topic

    reranker_config = {
        "enabled": settings.reranker_enabled,
        "model_name": settings.reranker_model,
        "max_rerank": settings.retrieval_top_k_db,
    }

    results = retrieve_top_k(
        connection,
        query,
        top_k=final_top_k,
        model_name=settings.embedding_model,
        min_score=0.0,
        reranker_config=reranker_config,
        top_k_db=settings.retrieval_top_k_db,
    )

    return [
        normalize_baseline_document(result)
        for result in results
    ]


def deduplicate_documents(
    documents: List[Dict[str, Any]],
    *,
    limit: int,
) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for document in documents:
        key = (
            str(document.get("object_id") or "")
            or str(document.get("source_url") or "")
            or str(document.get("id") or "")
        )

        if not key or key in seen:
            continue

        seen.add(key)
        output.append(document)

        if len(output) >= limit:
            break

    return output