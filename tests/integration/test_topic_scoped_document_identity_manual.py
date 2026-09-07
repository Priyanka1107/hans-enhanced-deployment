from __future__ import annotations

from app.email.service import _document_key
from app.retrieval.baseline_adapter import (
    deduplicate_documents,
)
from app.retrieval.document_identity import (
    evidence_document_key,
)


def main() -> None:
    url = "https://mpmd.htw-berlin.de/"

    language_doc = {
        "id": (
            "official_programme_page::"
            "Project Management and Data Science::"
            + url
            + "::language_of_instruction"
        ),
        "source_url": url,
        "url": url,
        "object_type":
            "official_programme_page_cache",
        "content":
            "Teaching language English.",
        "metadata": {
            "topic_id":
                "language_of_instruction",
        },
    }

    format_doc = {
        "id": (
            "official_programme_page::"
            "Project Management and Data Science::"
            + url
            + "::study_format"
        ),
        "source_url": url,
        "url": url,
        "object_type":
            "official_programme_page_cache",
        "content": (
            "Self-paced online learning. "
            "Lectures are simultaneously streamed "
            "as interactive video conferences."
        ),
        "metadata": {
            "topic_id": "study_format",
        },
    }

    language_key = evidence_document_key(
        language_doc
    )

    format_key = evidence_document_key(
        format_doc
    )

    if language_key == format_key:
        raise AssertionError(
            "Different topic-specific evidence "
            "from one official URL was collapsed."
        )

    if _document_key(language_doc) != language_key:
        raise AssertionError(
            "service.py is not using the shared "
            "evidence identity."
        )

    if _document_key(format_doc) != format_key:
        raise AssertionError(
            "service.py is not using the shared "
            "study-format evidence identity."
        )

    preserved = deduplicate_documents(
        [
            language_doc,
            format_doc,
        ],
        limit=10,
    )

    if len(preserved) != 2:
        raise AssertionError(
            "Baseline deduplication still collapses "
            "different official topic snippets."
        )

    same_topic_duplicate = (
        deduplicate_documents(
            [
                format_doc,
                dict(format_doc),
            ],
            limit=10,
        )
    )

    if len(same_topic_duplicate) != 1:
        raise AssertionError(
            "Exact same-topic duplicate was not removed."
        )

    generic_a = {
        "id": "generic-a",
        "source_url":
            "https://www.htw-berlin.de/example",
        "url":
            "https://www.htw-berlin.de/example",
        "object_type": "web",
        "content": "First generic chunk.",
    }

    generic_b = {
        "id": "generic-b",
        "source_url":
            "https://www.htw-berlin.de/example",
        "url":
            "https://www.htw-berlin.de/example",
        "object_type": "web",
        "content": "Second generic chunk.",
    }

    generic = deduplicate_documents(
        [
            generic_a,
            generic_b,
        ],
        limit=10,
    )

    if len(generic) != 1:
        raise AssertionError(
            "Generic same-URL deduplication changed."
        )

    print(
        "PASS: same-URL official evidence "
        "remains distinct by topic."
    )

    print(
        "PASS: same-topic duplicate evidence "
        "still collapses."
    )

    print(
        "PASS: generic same-URL deduplication "
        "remains unchanged."
    )

    print(
        "PASS: service and retrieval use "
        "one shared evidence identity."
    )


if __name__ == "__main__":
    main()
