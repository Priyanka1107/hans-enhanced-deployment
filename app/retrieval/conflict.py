from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.settings import settings


def _parse_dt(value: str) -> datetime:
    """
    Parse an ISO datetime value.

    Missing or invalid values are treated as very old so that newer,
    better-maintained sources are preferred.
    """
    try:
        return datetime.fromisoformat(
            str(value or "").replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return datetime(1970, 1, 1)


def detect_and_resolve_conflicts(
    documents: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Detect potential freshness conflicts and select the strongest source.

    Expected document fields may include:
    - id
    - title
    - content
    - source_url
    - category
    - object_type
    - last_updated
    - is_canonical
    - priority

    Returns:
    - final_documents
    - conflicts
    """

    by_category: Dict[str, List[Dict[str, Any]]] = {}

    for document in documents:
        category = str(
            document.get("category")
            or document.get("metadata", {}).get("topic_id")
            or ""
        ).strip()

        # Documents without a real category must not all be grouped together.
        # Give each uncategorised document its own group.
        if not category:
            unique_part = str(
                document.get("source_url")
                or document.get("url")
                or document.get("id")
                or document.get("object_id")
                or id(document)
            )

            category = f"uncategorized::{unique_part}"
        by_category.setdefault(category, []).append(document)

    conflicts: List[Dict[str, Any]] = []
    chosen_documents: List[Dict[str, Any]] = []
    remaining_documents: List[Dict[str, Any]] = []

    for category, category_documents in by_category.items():
        if len(category_documents) == 1:
            remaining_documents.append(category_documents[0])
            continue

        dates = [
            _parse_dt(
                str(document.get("last_updated") or "")
            )
            for document in category_documents
        ]

        gap_days = (
            (max(dates) - min(dates)).days
            if dates
            else 0
        )

        if gap_days > 180:
            conflicts.append(
                {
                    "type": "timestamp_conflict",
                    "category": category,
                    "doc_ids": [
                        document.get("id")
                        for document in category_documents
                    ],
                    "gap_days": gap_days,
                    "oldest": min(dates).isoformat(),
                    "newest": max(dates).isoformat(),
                    "message": (
                        f"Multiple sources in '{category}' differ "
                        f"in recency by {gap_days} days; using "
                        "canonical, freshness and priority rules."
                    ),
                }
            )

            def score(
                document: Dict[str, Any],
            ) -> tuple[bool, datetime, int, int]:
                return (
                    bool(
                        document.get(
                            "is_canonical",
                            False,
                        )
                    ),
                    _parse_dt(
                        str(
                            document.get(
                                "last_updated",
                                "",
                            )
                        )
                    ),
                    settings.object_type_priority.get(
                        str(
                            document.get(
                                "object_type",
                                "",
                            )
                        ),
                        0,
                    ),
                    int(
                        document.get(
                            "priority",
                            0,
                        )
                        or 0
                    ),
                )

            best_document = max(
                category_documents,
                key=score,
            )

            best_document = dict(best_document)

            best_document["conflict_alternatives"] = [
                {
                    "id": alternative.get("id"),
                    "title": alternative.get("title"),
                    "last_updated": alternative.get(
                        "last_updated"
                    ),
                    "object_type": alternative.get(
                        "object_type"
                    ),
                    "reason": "lower_priority",
                }
                for alternative in category_documents
                if alternative.get("id")
                != best_document.get("id")
            ]

            chosen_documents.append(best_document)

        else:
            remaining_documents.extend(category_documents)

    final_documents = (
        chosen_documents + remaining_documents
    )

    return final_documents, conflicts