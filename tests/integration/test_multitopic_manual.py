from __future__ import annotations

from pprint import pprint
from typing import Any

from app.email.multitopic import (
    detect_topics,
    extract_email_context,
)
from app.knowledge.programme_context import (
    enrich_email_text_with_programme_context,
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

    print("\nPROGRAMME RESULT")
    print("=" * 80)
    pprint(programme_result)

    print("\nEMAIL CONTEXT")
    print("=" * 80)
    pprint(context)

    print("\nDETECTED TOPICS")
    print("=" * 80)

    for index, topic in enumerate(topics, start=1):
        print(f"\nTopic {index}")
        pprint(topic)

    topic_ids = {
        str(topic.get("topic_id") or "")
        for topic in topics
    }

    expected_topics = {
        "application_deadline",
        "language_of_instruction",
        "study_format",
        "required_documents",
    }

    missing_topics = expected_topics - topic_ids

    print("\nSUMMARY")
    print("=" * 80)
    print(f"Detected topic IDs: {sorted(topic_ids)}")
    print(f"Missing expected topics: {sorted(missing_topics)}")

    if missing_topics:
        raise AssertionError(
            "Multi-topic detection missed expected topics: "
            + ", ".join(sorted(missing_topics))
        )

    print("Multi-topic detection passed.")


if __name__ == "__main__":
    main()