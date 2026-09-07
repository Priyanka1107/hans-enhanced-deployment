from __future__ import annotations

from app.knowledge.programme_official_evidence import (
    get_official_programme_docs,
)


def text_of(document):
    return str(
        document.get("content")
        or document.get("chunk_text")
        or ""
    ).lower()


def main() -> None:
    context = {
        "target_program": (
            "Project Management and Data Science"
        ),
        "target_programme": (
            "Project Management and Data Science"
        ),
        "matched_programme": (
            "Project Management and Data Science"
        ),
        "target_program_url": (
            "http://mpmd.htw-berlin.de/en/?no_cache=1"
        ),
        "matched_programme_url": (
            "http://mpmd.htw-berlin.de/en/?no_cache=1"
        ),
        "target_degree": "Master",
        "catalog_degree": "Master",
    }

    # -----------------------------------------------------
    # Language of instruction
    # -----------------------------------------------------

    language_docs = get_official_programme_docs(
        context,
        "language_of_instruction",
        10,
    )

    if not language_docs:
        raise AssertionError(
            "No language-of-instruction evidence returned."
        )

    if not any(
        "english-taught" in text_of(doc)
        or "taught in english" in text_of(doc)
        or "teaching language" in text_of(doc)
        or "language of instruction" in text_of(doc)
        for doc in language_docs
    ):
        raise AssertionError(
            "No genuine teaching-language evidence found."
        )

    for doc in language_docs:
        content = text_of(doc)

        proof_only = (
            (
                "toefl" in content
                or "ielts" in content
                or "proof of english" in content
                or "english proficiency" in content
            )
            and not (
                "english-taught" in content
                or "taught in english" in content
                or "teaching language" in content
                or "language of instruction" in content
            )
        )

        if proof_only:
            raise AssertionError(
                "English-proof evidence leaked into "
                "language_of_instruction."
            )

    language_urls = [
        str(doc.get("url") or "").lower().rstrip("/")
        for doc in language_docs
    ]

    if len(language_urls) != len(set(language_urls)):
        raise AssertionError(
            "Duplicate official URLs were returned for "
            "language_of_instruction."
        )

    # -----------------------------------------------------
    # Study format
    # -----------------------------------------------------

    format_docs = get_official_programme_docs(
        context,
        "study_format",
        10,
    )

    if not format_docs:
        raise AssertionError(
            "No study-format evidence returned."
        )

    if not any(
        "online learning" in text_of(doc)
        or "online participation" in text_of(doc)
        or "simultaneously streamed" in text_of(doc)
        or "interactive video conference" in text_of(doc)
        for doc in format_docs
    ):
        raise AssertionError(
            "Genuine MPMD teaching-format evidence "
            "was not preserved."
        )

    for doc in format_docs:
        content = text_of(doc)

        if (
            "online application form" in content
            and not (
                "online learning" in content
                or "online participation" in content
                or "simultaneously streamed" in content
                or "interactive video conference" in content
            )
        ):
            raise AssertionError(
                "Online-application wording was incorrectly "
                "used as study-format evidence."
            )

    format_urls = [
        str(doc.get("url") or "").lower().rstrip("/")
        for doc in format_docs
    ]

    if len(format_urls) != len(set(format_urls)):
        raise AssertionError(
            "Duplicate official URLs were returned for "
            "study_format."
        )

    # -----------------------------------------------------
    # Deadline
    # -----------------------------------------------------

    deadline_docs = get_official_programme_docs(
        context,
        "application_deadline",
        10,
    )

    if not deadline_docs:
        raise AssertionError(
            "No MPMD deadline evidence returned."
        )

    if not any(
        "application period" in text_of(doc)
        or "application deadline" in text_of(doc)
        or "apply by" in text_of(doc)
        for doc in deadline_docs
    ):
        raise AssertionError(
            "Deadline evidence lacks a real "
            "application-period/deadline statement."
        )

    deadline_urls = [
        str(doc.get("url") or "").lower().rstrip("/")
        for doc in deadline_docs
    ]

    if len(deadline_urls) != len(set(deadline_urls)):
        raise AssertionError(
            "Duplicate official URLs were returned for "
            "application_deadline."
        )

    print(
        "PASS: duplicate official programme URLs "
        "are removed."
    )

    print(
        "PASS: teaching language uses genuine "
        "teaching-language evidence."
    )

    print(
        "PASS: English-proof evidence is not accepted "
        "as teaching-language evidence."
    )

    print(
        "PASS: genuine MPMD study-format evidence "
        "is preserved."
    )

    print(
        "PASS: online-application wording is not "
        "treated as study format."
    )

    print(
        "PASS: MPMD deadline evidence is "
        "topic-specific."
    )


if __name__ == "__main__":
    main()
