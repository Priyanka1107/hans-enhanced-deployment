from __future__ import annotations

from app.email.service import _remove_unasked_topic_content


def _check(
    name: str,
    draft: str,
    topics: list[dict[str, str]],
    original_email: str,
    *,
    must_keep: tuple[str, ...] = (),
    must_remove: tuple[str, ...] = (),
) -> None:
    cleaned = _remove_unasked_topic_content(
        draft,
        topics,
        original_email,
    )

    lower = cleaned.lower()

    for phrase in must_keep:
        if phrase.lower() not in lower:
            raise AssertionError(
                f"{name}: expected to keep {phrase!r}. "
                f"Output: {cleaned!r}"
            )

    for phrase in must_remove:
        if phrase.lower() in lower:
            raise AssertionError(
                f"{name}: expected to remove {phrase!r}. "
                f"Output: {cleaned!r}"
            )

    print(f"PASS: {name}")


def main() -> None:
    # ---------------------------------------------------------
    # Preserve legitimate content for the topic actually asked.
    # ---------------------------------------------------------

    _check(
        "language answer preserved",
        "The courses in this programme are taught in English [Doc 1].",
        [{"topic_id": "language_of_instruction"}],
        "Is the programme taught in English?",
        must_keep=("taught in English",),
    )

    _check(
        "study-format answer preserved",
        "These courses are delivered online [Doc 1].",
        [{"topic_id": "study_format"}],
        "Is the programme online or on campus?",
        must_keep=("delivered online",),
    )

    _check(
        "required-documents work proof preserved",
        "Please submit proof of at least one year of professional experience [Doc 1].",
        [{"topic_id": "required_documents"}],
        "Which documents are required?",
        must_keep=("professional experience",),
    )

    _check(
        "document-upload work proof preserved",
        "Please upload proof of your professional experience [Doc 1].",
        [{"topic_id": "document_uploads"}],
        "Which documents should I upload?",
        must_keep=("professional experience",),
    )

    _check(
        "required-documents English proof preserved",
        "Please submit proof of English language proficiency [Doc 1].",
        [{"topic_id": "required_documents"}],
        "Which documents are required?",
        must_keep=("English language proficiency",),
    )

    _check(
        "document-upload English proof preserved",
        "Please upload your English language proficiency certificate [Doc 1].",
        [{"topic_id": "document_uploads"}],
        "Which documents should I upload?",
        must_keep=("English language proficiency",),
    )

    _check(
        "admission requirement preserved when asked",
        "For admission, you need a bachelor's degree with at least 180 ECTS [Doc 1].",
        [{"topic_id": "admission_requirements"}],
        "What are the admission requirements?",
        must_keep=("180 ECTS",),
    )

    _check(
        "work-experience requirement preserved when asked",
        "You need at least one year of professional experience [Doc 1].",
        [{"topic_id": "work_experience"}],
        "What work experience is required?",
        must_keep=("professional experience",),
    )

    _check(
        "English-proof requirement preserved when asked",
        "Please provide proof of English language proficiency [Doc 1].",
        [{"topic_id": "english_language_requirements"}],
        "What English language proof is required?",
        must_keep=("English language proficiency",),
    )

    # ---------------------------------------------------------
    # Remove clearly unasked content.
    # ---------------------------------------------------------

    _check(
        "eligibility removed from required-documents answer",
        (
            "Regarding your eligibility for the programme, "
            "you need a bachelor's degree with at least 180 ECTS."
        ),
        [{"topic_id": "required_documents"}],
        "Which documents are required?",
        must_remove=(
            "eligibility for the programme",
            "180 ECTS",
        ),
    )

    _check(
        "work experience removed from language-only answer",
        "You must provide at least one year of professional experience.",
        [{"topic_id": "language_of_instruction"}],
        "Is the programme taught in English?",
        must_remove=("professional experience",),
    )

    _check(
        "dependent requirement sentence removed",
        (
            "According to [Doc 2], the programme requires you to "
            "submit proof of at least one year of professional experience. "
            "This requirement is also mentioned in [Doc 1]."
        ),
        [
            {"topic_id": "language_of_instruction"},
            {"topic_id": "study_format"},
        ],
        (
            "Is the programme taught completely in English, "
            "and is it offered online or on campus?"
        ),
        must_remove=(
            "professional experience",
            "This requirement",
        ),
    )

    _check(
        "generic eligibility-suitability advice removed",
        (
            "Please note that while we have provided some information "
            "about the programme, the official application review will "
            "determine your eligibility and suitability for the programme. "
            "We recommend checking the complete application information "
            "on our website for more details."
        ),
        [
            {"topic_id": "language_of_instruction"},
            {"topic_id": "study_format"},
        ],
        (
            "Is the programme taught completely in English, "
            "and is it offered online or on campus?"
        ),
        must_keep=("complete application information",),
        must_remove=("eligibility and suitability",),
    )

    # ---------------------------------------------------------
    # Preserve application-route behavior while continuing
    # cleanup of unrelated content.
    # ---------------------------------------------------------

    route_sentence = (
        "Applications are accepted only via the HTW "
        "application portal or uni-assist, depending on "
        "your eligibility criteria."
    )

    _check(
        "application-route answer preserved",
        route_sentence,
        [{"topic_id": "application_route"}],
        "How do I apply?",
        must_keep=("uni-assist",),
    )

    _check(
        "route plus language removes unrelated work advice",
        (
            route_sentence
            + "\n\nThe programme is taught in English [Doc 1]."
            + "\n\nYou must provide at least one year of "
            "professional experience."
        ),
        [
            {"topic_id": "application_route"},
            {"topic_id": "language_of_instruction"},
        ],
        "How do I apply, and is the programme taught in English?",
        must_keep=(
            "uni-assist",
            "taught in English",
        ),
        must_remove=("professional experience",),
    )

    # ---------------------------------------------------------
    # Scholarship cleanup must not remove unrelated DAAD
    # admissions/recognition guidance.
    # ---------------------------------------------------------

    _check(
        "unasked scholarship removed",
        "We recommend checking the DAAD website for possible scholarships.",
        [{"topic_id": "language_of_instruction"}],
        "Is the programme taught in English?",
        must_remove=("scholarship",),
    )

    _check(
        "asked scholarship preserved",
        "You can find information about scholarships on the DAAD website.",
        [{"topic_id": "programme_overview"}],
        "Are there any scholarships or funding options available?",
        must_keep=("scholarships",),
    )

    _check(
        "DAAD admissions guidance preserved",
        (
            "Please check the DAAD website and admissions database "
            "for information about recognition of your qualification."
        ),
        [{"topic_id": "qualification_recognition"}],
        "How can I check recognition of my qualification?",
        must_keep=(
            "DAAD website",
            "recognition of your qualification",
        ),
    )

    # ---------------------------------------------------------
    # Regression based on Q1 draft-quality failure.
    # Scope cleanup must remove only the unrelated material.
    # ---------------------------------------------------------

    q1_bad_draft = """Dear Rahul,

Regarding your question about the language of instruction, our official programme page [Doc 1] states that the programme is "English-taught". This means that all lectures and coursework will be conducted in English.

As for the study format, we do not explicitly state whether it is offered online or on-campus.

According to [Doc 2], the programme requires you to submit proof of at least one year of professional experience, which suggests that some form of attendance may be required.

Regarding your eligibility for the programme, we require a bachelor's degree with at least 180 ECTS, as well as proof of English language proficiency.

We also recommend checking the DAAD website for possible scholarships.
"""

    _check(
        "Q1 scope regression",
        q1_bad_draft,
        [
            {"topic_id": "language_of_instruction"},
            {"topic_id": "study_format"},
        ],
        (
            "Is the programme taught completely in English, "
            "and is it offered online or on campus?"
        ),
        must_keep=(
            "English-taught",
            "online or on-campus",
        ),
        must_remove=(
            "professional experience",
            "eligibility for the programme",
            "180 ECTS",
            "English language proficiency",
            "scholarships",
        ),
    )

    print()
    print("=" * 72)
    print("PASS: all scope-cleanup regression checks passed.")
    print("=" * 72)


if __name__ == "__main__":
    main()
