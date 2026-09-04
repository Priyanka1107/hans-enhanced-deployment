from __future__ import annotations

from app.knowledge.programme_official_evidence import (
    get_official_programme_docs,
)


def main() -> None:
    context = {
        "target_program": "Project Management and Data Science",
        "target_programme": "Project Management and Data Science",
        "matched_programme": "Project Management and Data Science",
        "target_program_url": (
            "http://mpmd.htw-berlin.de/en/?no_cache=1"
        ),
        "matched_programme_url": (
            "http://mpmd.htw-berlin.de/en/?no_cache=1"
        ),
        "target_degree": "Master",
        "catalog_degree": "Master",
    }

    documents = get_official_programme_docs(
        context,
        "study_format",
        10,
    )

    if not documents:
        raise AssertionError(
            "No official study-format evidence was returned."
        )

    homepage_evidence_found = False

    for document in documents:
        url = str(document.get("url") or "").lower()

        text = str(
            document.get("content")
            or document.get("chunk_text")
            or ""
        ).lower()

        if (
            "/applying" in url
            and "online application form" in text
        ):
            raise AssertionError(
                "Application-form wording was incorrectly "
                "selected as study-format evidence."
            )

        if (
            "mpmd.htw-berlin.de" in url
            and "/applying" not in url
            and (
                "online learning" in text
                or
                "lectures will simultaneously be streamed"
                in text
            )
        ):
            homepage_evidence_found = True

    if not homepage_evidence_found:
        raise AssertionError(
            "Expected MPMD teaching-format evidence "
            "was not preserved."
        )

    print(
        "PASS: online application wording is not used "
        "as study-format evidence."
    )

    print(
        "PASS: genuine MPMD teaching-format evidence "
        "is preserved."
    )

    print()
    print(
        "PASS: study-format evidence regression passed."
    )


if __name__ == "__main__":
    main()
