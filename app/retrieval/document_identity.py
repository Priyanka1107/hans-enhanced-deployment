from __future__ import annotations

from typing import Any, Dict


_TOPIC_SCOPED_OBJECT_TYPES = {
    "official_programme_page_cache",
    "programme_official_page",
    "official_degree_index",
}


def evidence_document_key(document: Dict[str, Any]) -> str:
    """Return a stable evidence identity without dropping topic-scoped snippets.

    Official programme evidence may intentionally expose more than one snippet
    from the same URL when different student topics need different sections of
    that page. Those records carry ``metadata.topic_id`` and must remain
    distinct through deduplication. Generic retrieval chunks retain the older
    URL/object identity behaviour.
    """
    metadata = (
        document.get("metadata", {})
        if isinstance(document.get("metadata"), dict)
        else {}
    )
    topic_id = str(metadata.get("topic_id") or "").strip().lower()
    object_type = str(document.get("object_type") or "").strip().lower()

    identifier = str(document.get("id") or "").strip()
    url = str(
        document.get("source_url")
        or document.get("url")
        or ""
    ).strip().lower().rstrip("/")

    if topic_id and object_type in _TOPIC_SCOPED_OBJECT_TYPES:
        if identifier:
            return f"topic_evidence::{identifier}"
        if url:
            return f"topic_url::{url}::{topic_id}"

    if url:
        return f"url::{url}"

    object_id = str(document.get("object_id") or "").strip()
    if object_id:
        return f"object::{object_id}"

    if identifier:
        return f"id::{identifier}"

    content = str(
        document.get("content")
        or document.get("chunk_text")
        or ""
    ).strip()
    if content:
        return f"content::{content[:240]}"

    return ""
