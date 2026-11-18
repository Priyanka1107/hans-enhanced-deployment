from app.email.service import (
    _find_source_applicability_issues,
    _find_topic_coverage_issues,
)


def test_late_language_submission_question_must_be_answered_directly() -> None:
    email = (
        "I have completed the IB Diploma in English. "
        "Can I submit an approved language certificate later, "
        "after the application deadline or upon conditional acceptance?"
    )

    topics = [
        {
            "topic_id": "english_language_requirements",
            "label": "English language requirements",
        }
    ]

    draft = (
        "The programme page does not list an English language proof "
        "requirement. The programme is taught in German."
    )

    issues = _find_topic_coverage_issues(
        draft,
        topics,
        email,
    )

    assert any(
        issue.startswith("question_not_directly_answered:")
        for issue in issues
    )


def test_late_language_submission_question_passes_when_addressed() -> None:
    email = (
        "Can I submit an approved language certificate later, "
        "after the application deadline or upon conditional acceptance?"
    )

    topics = [
        {
            "topic_id": "english_language_requirements",
            "label": "English language requirements",
        }
    ]

    draft = (
        "The programme page does not list an English language proof "
        "requirement. Therefore, submitting an English certificate at a "
        "later date does not appear applicable to this programme."
    )

    issues = _find_topic_coverage_issues(
        draft,
        topics,
        email,
    )

    assert not any(
        issue.startswith("question_not_directly_answered:")
        for issue in issues
    )


def test_general_retrieval_without_official_programme_evidence_is_flagged() -> None:
    topics = [
        {
            "topic_id": "english_language_requirements",
            "label": "English language requirements",
            "official_source_count": 0,
            "retrieved_source_count": 6,
            "source_count": 3,
        }
    ]

    issues = _find_source_applicability_issues(
        topics
    )

    assert len(issues) == 1
    assert issues[0].startswith(
        "source_applicability_review:"
    )


def test_official_programme_evidence_avoids_source_applicability_flag() -> None:
    topics = [
        {
            "topic_id": "english_language_requirements",
            "label": "English language requirements",
            "official_source_count": 1,
            "retrieved_source_count": 6,
            "source_count": 3,
        }
    ]

    assert _find_source_applicability_issues(
        topics
    ) == []
