from app.email.service import (
    _find_claim_support_issues,
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


def test_presence_study_classification_answers_on_campus_delivery_question() -> None:
    email = "Is the programme on campus?"

    topics = [
        {
            "topic_id": "study_format",
            "label": "Study format",
        }
    ]

    draft = (
        'The official HTW study classification is "Präsenzstudium" '
        "(presence study). The programme also includes self-paced "
        "online learning components."
    )

    issues = _find_topic_coverage_issues(
        draft,
        topics,
        email,
    )

    assert not any(
        issue.startswith("topic_not_answered: study_format")
        for issue in issues
    )


def test_campus_location_plus_online_component_still_does_not_answer_delivery_mode() -> None:
    email = "Is the programme online or on campus?"

    topics = [
        {
            "topic_id": "study_format",
            "label": "Study format",
        }
    ]

    draft = (
        "The programme is full-time. The location is HTW Berlin, "
        "Treskowallee Campus. It includes self-paced online learning."
    )

    issues = _find_topic_coverage_issues(
        draft,
        topics,
        email,
    )

    assert any(
        issue.startswith("topic_not_answered: study_format")
        for issue in issues
    )

def test_online_application_wording_is_not_a_study_format_claim() -> None:
    draft = (
        "You can apply for a higher subject semester if this option "
        "is offered for the specific study programme in the online "
        "application [Doc 1]."
    )

    documents = [
        {
            "title": "Changing study programme or university",
            "url": (
                "https://www.htw-berlin.de/en/studies/applications/"
                "special-cases/changing-study-programme-or-university/"
            ),
            "content": (
                "Applicants may apply for a higher subject semester "
                "where this option is available in the online application."
            ),
        }
    ]

    issues = _find_claim_support_issues(
        draft,
        documents,
    )

    assert not any(
        issue.startswith("study_format:")
        for issue in issues
    )



def test_before_graduation_without_official_programme_evidence_is_flagged() -> None:
    topics = [
        {
            "topic_id": "application_before_graduation",
            "label": "Application before graduation",
            "official_source_count": 0,
            "retrieved_source_count": 6,
            "source_count": 1,
        }
    ]

    issues = _find_source_applicability_issues(
        topics
    )

    assert len(issues) == 1
    assert issues[0].startswith(
        "source_applicability_review:"
    )


def test_unresolved_before_graduation_answer_requires_review() -> None:
    email = (
        "I am still completing my Bachelor's degree. "
        "Can I apply before receiving my final degree certificate?"
    )

    topics = [
        {
            "topic_id": "application_before_graduation",
            "label": "Application before graduation",
        }
    ]

    draft = (
        "The provided evidence does not explicitly state whether "
        "applicants may submit their application before receiving "
        "their final degree certificate. Therefore, I cannot confirm "
        "from the available official sources whether provisional "
        "transcripts are accepted."
    )

    issues = _find_topic_coverage_issues(
        draft,
        topics,
        email,
    )

    assert any(
        issue.startswith(
            "topic_unresolved: application_before_graduation"
        )
        for issue in issues
    )
