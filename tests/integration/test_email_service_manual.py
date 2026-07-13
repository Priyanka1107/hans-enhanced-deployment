from __future__ import annotations

import asyncio
import re
import uuid
from pprint import pprint
from urllib.parse import urlparse

from app.email.service import EmailAssistantService
from hansdb.conn import get_db_connection, load_config


EXPECTED_URL = (
    "https://f2ki-h100-1.f2.htw-berlin.de:11435"
)
EXPECTED_MODEL = "qwen3:32b"

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


def _normalise_url(url: str) -> str:
    parsed = urlparse(
        str(url or "").strip()
    )

    host = parsed.netloc.lower()

    if host.startswith("www."):
        host = host[4:]

    path = re.sub(
        r"/+",
        "/",
        parsed.path,
    ).rstrip("/")

    return f"{host}{path}".lower()


async def main() -> None:
    config = load_config()
    connection = get_db_connection(config)

    try:
        service = EmailAssistantService(
            connection
        )

        print("\nGENERATION RUNTIME")
        print("=" * 100)
        print(
            "Client class:",
            service.llm.__class__.__name__,
        )
        print(
            "Endpoint:",
            service.llm.base_url,
        )
        print(
            "Model:",
            service.llm.model,
        )
        print(
            "SSL verification:",
            service.llm.verify_ssl,
        )
        print(
            "Timeout:",
            service.llm.timeout,
        )
        print(
            "Maximum attempts:",
            service.llm.max_attempts,
        )
        print(
            "Expected endpoint:",
            EXPECTED_URL,
        )
        print(
            "Expected model:",
            EXPECTED_MODEL,
        )

        if service.llm.base_url != EXPECTED_URL:
            raise AssertionError(
                "The email pipeline is not using the "
                "expected HTW Ollama endpoint. Got: "
                f"{service.llm.base_url}"
            )

        if service.llm.model != EXPECTED_MODEL:
            raise AssertionError(
                "The email pipeline is not using "
                f"qwen3:32b. Got: {service.llm.model}"
            )

        if service.llm.verify_ssl is not True:
            raise AssertionError(
                "SSL verification must be enabled for HTW."
            )

        run_id = uuid.uuid4().hex[:12]

        result = await service.process_email(
            email_text=EMAIL,
            student_email="arjun@example.com",
            subject="MPMD application questions",
            thread_id=(
                f"htw-qwen-thread-{run_id}"
            ),
            email_id=(
                f"htw-qwen-email-{run_id}"
            ),
            language="en",
            top_k=6,
        )

        print("\nRESULT SUMMARY")
        print("=" * 100)
        print(
            "Follow-up type:",
            result.get("followup_type"),
        )
        print(
            "Flagged for human:",
            result.get("flagged_for_human"),
        )
        print(
            "Automatic send:",
            result.get("automatic_send"),
        )

        print("\nEMAIL CONTEXT")
        print("=" * 100)
        pprint(
            result.get("email_context")
        )

        print("\nDETECTED TOPICS")
        print("=" * 100)
        pprint(
            result.get("detected_topics")
        )

        print("\nSOURCES")
        print("=" * 100)

        for index, source in enumerate(
            result.get("sources", []),
            start=1,
        ):
            print(f"\nSource {index}")
            print(
                "Title:",
                source.get("title"),
            )
            print(
                "URL:",
                source.get("url"),
            )
            print(
                "Type:",
                source.get("type"),
            )
            print(
                "Excerpt:",
                str(
                    source.get("excerpt")
                    or ""
                )[:300],
            )

        print("\nVALIDATION")
        print("=" * 100)
        pprint(
            result.get("validation")
        )

        print("\nQUALITY")
        print("=" * 100)
        pprint(
            result.get("quality")
        )

        print("\nSTAFF DRAFT")
        print("=" * 100)
        staff_draft = str(
            result.get("staff_draft")
            or ""
        )
        print(staff_draft)

        expected_topics = {
            "application_deadline",
            "required_documents",
            "language_of_instruction",
            "study_format",
        }

        detected_topics = {
            str(
                topic.get("topic_id")
                or ""
            )
            for topic in result.get(
                "detected_topics",
                [],
            )
        }

        missing_topics = (
            expected_topics
            - detected_topics
        )

        if missing_topics:
            raise AssertionError(
                "Missing expected topics: "
                + ", ".join(
                    sorted(missing_topics)
                )
            )

        if (
            result.get("followup_type")
            != "new_enquiry"
        ):
            raise AssertionError(
                "A unique test thread should be "
                "classified as new_enquiry. Got: "
                f"{result.get('followup_type')}"
            )

        if (
            result.get("automatic_send")
            is not False
        ):
            raise AssertionError(
                "automatic_send must always "
                "be False."
            )

        if not staff_draft.strip():
            raise AssertionError(
                "No staff draft was generated."
            )

        if not result.get("sources"):
            raise AssertionError(
                "No supporting sources were returned."
            )

        lower_draft = staff_draft.lower()

        if "dear htw berlin staff" in lower_draft:
            raise AssertionError(
                "The draft was addressed to staff "
                "instead of the student."
            )

        if "dear arjun" not in lower_draft:
            raise AssertionError(
                "The draft does not address Arjun."
            )

        body_before_references = staff_draft.split(
            "Reference links for staff verification:",
            1,
        )[0]

        if re.search(
            r"^\s*subject\s*:",
            body_before_references,
            flags=re.IGNORECASE
            | re.MULTILINE,
        ):
            raise AssertionError(
                "A Subject line was generated "
                "inside the email body."
            )

        source_urls = {
            _normalise_url(
                source.get("url") or ""
            )
            for source in result.get(
                "sources",
                [],
            )
        }

        required_source_urls = {
            "mpmd.htw-berlin.de/applying",
            "mpmd.htw-berlin.de",
        }

        missing_sources = (
            required_source_urls
            - source_urls
        )

        if missing_sources:
            raise AssertionError(
                "The final evidence pack is missing "
                "the direct programme source(s): "
                + ", ".join(
                    sorted(missing_sources)
                )
            )

        validation = (
            result.get("validation")
            or {}
        )

        if validation.get(
            "failure_type"
        ):
            print("\nQUALITY NOTICE")
            print("-" * 100)
            print(
                "The technical pipeline passed, "
                "but validation still reported:",
                validation.get(
                    "failure_type"
                ),
            )
            print(
                "This result remains visible and "
                "must be reviewed separately."
            )

        print("\nTEST RESULT")
        print("=" * 100)
        print(
            "PASS: Complete HTW Qwen "
            "email-service pipeline test passed."
        )
        print(
            "Generation endpoint:",
            service.llm.base_url,
        )
        print(
            "Generation model:",
            service.llm.model,
        )

    finally:
        connection.close()


if __name__ == "__main__":
    asyncio.run(main())
