from __future__ import annotations

from pprint import pprint
from typing import Any

from app.knowledge.programme_official_evidence import (
    get_official_programme_docs,
)


def main() -> None:
    context: dict[str, Any] = {
        "target_program": "Project Management and Data Science",
        "target_programme": "Project Management and Data Science",
        "matched_programme": "Project Management and Data Science",
        "target_program_url": "https://mpmd.htw-berlin.de/",
        "matched_programme_url": "https://mpmd.htw-berlin.de/",
        "target_program_application_url": (
            "https://mpmd.htw-berlin.de/applying"
        ),
    }

    topic_id = "application_deadline"

    documents = get_official_programme_docs(
        context,
        topic_id,
        5,
    )

    print(f"Programme: {context['target_program']}")
    print(f"Topic: {topic_id}")
    print(f"Documents returned: {len(documents)}")

    if not documents:
        raise RuntimeError(
            "No official programme evidence was returned."
        )

    seen_urls: set[str] = set()

    for index, document in enumerate(documents, start=1):
        url = str(
            document.get("source_url")
            or document.get("url")
            or ""
        ).rstrip("/")

        title = str(document.get("title") or "")
        content = str(
            document.get("content")
            or document.get("chunk_text")
            or ""
        )

        duplicate = bool(url and url.lower() in seen_urls)

        if url:
            seen_urls.add(url.lower())

        print("\n" + "=" * 80)
        print(f"Document {index}")
        print(f"Title: {title}")
        print(f"URL: {url}")
        print(f"Duplicate URL: {duplicate}")
        print(f"Object type: {document.get('object_type', '')}")
        print(f"Score: {document.get('score', '')}")
        print("Content preview:")
        print(content[:800])

        print("\nFull document:")
        pprint(document)

    duplicate_count = len(documents) - len(seen_urls)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print(f"Returned documents: {len(documents)}")
    print(f"Unique URLs: {len(seen_urls)}")
    print(f"Duplicate URLs: {duplicate_count}")


if __name__ == "__main__":
    main()