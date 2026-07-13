from __future__ import annotations

from pprint import pprint
from typing import Any

from hansdb.conn import (
    get_db_connection,
    load_config,
)

from app.email.multitopic import (
    build_evidence_query,
    detect_topics,
    extract_email_context,
    filter_docs_for_programme,
)
from app.knowledge.programme_context import (
    enrich_email_text_with_programme_context,
)
from app.knowledge.programme_official_evidence import (
    get_official_programme_docs,
)
from app.retrieval.baseline_adapter import (
    deduplicate_documents,
    retrieve_for_topic,
)


EMAIL = """
Dear Admissions Team,

I would like to apply for the Master's programme in
Project Management and Data Science.

Could you please tell me:

1. What is the application deadline?
2. Is the programme taught entirely in English?
3. Is it an on-campus programme?
4. Which application documents are required?

Kind regards,
Arjun
""".strip()


def document_url(document: dict[str, Any]) -> str:
    return str(
        document.get("source_url")
        or document.get("url")
        or ""
    )


def main() -> None:
    programme_result = enrich_email_text_with_programme_context(
        email_text=EMAIL,
        subject="MPMD application questions",
    )

    enriched_email = programme_result.get(
        "enriched_email_text",
        EMAIL,
    )

    context: dict[str, Any] = extract_email_context(
        enriched_email
    )

    programme_name = str(
        programme_result.get("program_name") or ""
    )

    if programme_name:
        context["target_program"] = programme_name
        context["target_programme"] = programme_name
        context["matched_programme"] = programme_name

    programme_url = str(
        programme_result.get("url") or ""
    )

    if programme_url:
        context["target_program_url"] = programme_url
        context["matched_programme_url"] = programme_url

    application_url = str(
        programme_result.get("application_url") or ""
    )

    if application_url:
        context[
            "target_program_application_url"
        ] = application_url

    topics = detect_topics(
        enriched_email,
        context,
        max_topics=6,
    )

    print("\nPROGRAMME")
    print("=" * 100)
    pprint(programme_result)

    print("\nCONTEXT")
    print("=" * 100)
    pprint(context)

    print("\nTOPICS")
    print("=" * 100)
    pprint(topics)

    config = load_config()
    connection = get_db_connection(config)

    try:
        for topic in topics:
            topic_id = str(
                topic.get("topic_id") or ""
            )

            base_query = str(
                topic.get("base_query")
                or topic.get("query")
                or EMAIL
            )

            evidence_query = build_evidence_query(
                topic_id,
                base_query,
                context,
            )

            baseline_documents = retrieve_for_topic(
                connection=connection,
                query=evidence_query,
                top_k=8,
            )

            official_documents = get_official_programme_docs(
                context,
                topic_id,
                4,
            )

            combined_documents = (
                official_documents
                + baseline_documents
            )

            filtered_documents = filter_docs_for_programme(
                combined_documents,
                context,
                topic_id=topic_id,
                min_keep=3,
            )

            final_documents = deduplicate_documents(
                filtered_documents,
                limit=6,
            )

            print("\n" + "=" * 100)
            print(f"TOPIC: {topic_id}")
            print(f"QUERY: {evidence_query}")
            print(
                f"Official sources: "
                f"{len(official_documents)}"
            )
            print(
                f"Baseline sources: "
                f"{len(baseline_documents)}"
            )
            print(
                f"Final sources: "
                f"{len(final_documents)}"
            )

            for index, document in enumerate(
                final_documents,
                start=1,
            ):
                print("\n" + "-" * 80)
                print(f"Result {index}")
                print(
                    "Title:",
                    document.get("title", ""),
                )
                print(
                    "URL:",
                    document_url(document),
                )
                print(
                    "Object type:",
                    document.get("object_type", ""),
                )
                print(
                    "Score:",
                    document.get("score", ""),
                )

                content = str(
                    document.get("content")
                    or document.get("chunk_text")
                    or ""
                )

                print(
                    "Preview:",
                    content[:400].replace("\n", " "),
                )

    finally:
        connection.close()


if __name__ == "__main__":
    main()