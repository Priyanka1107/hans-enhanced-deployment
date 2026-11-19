from app.email.multitopic import (
    build_evidence_query,
    detect_topics,
    filter_docs_for_programme,
)
from app.email.service import (
    _build_credit_geographic_scope_guidance,
    _find_topic_coverage_issues,
)


INTERNATIONAL_BUSINESS_TRANSFER_EMAIL = """
I am currently studying International Business at HAMK in Finland,
where I have successfully completed 73 ECTS credits so far.

I would like to ask if I may apply either as a new applicant or as a
transfer student, and whether it would be possible to recognize some of
my completed credits.

Could you kindly advise on the appropriate path and the required
documents for my application?
""".strip()


def _topic_ids(email_text: str) -> set[str]:
    topics = detect_topics(
        email_text,
        context={
            "target_program": "International Business",
        },
        max_topics=6,
    )

    return {
        str(topic.get("topic_id") or "")
        for topic in topics
    }


def test_detects_credit_recognition_in_active_student_wording() -> None:
    topic_ids = _topic_ids(
        INTERNATIONAL_BUSINESS_TRANSFER_EMAIL
    )

    assert "credit_recognition" in topic_ids


def test_detects_higher_semester_credit_transfer_wording() -> None:
    topic_ids = _topic_ids(
        "Can my completed modules be recognised so that I can "
        "enter a higher semester?"
    )

    assert "credit_recognition" in topic_ids


def test_completed_ects_background_alone_does_not_imply_transfer() -> None:
    topic_ids = _topic_ids(
        "I am currently studying in Finland and have completed "
        "73 ECTS credits so far. What is the application deadline?"
    )

    assert "credit_recognition" not in topic_ids


def test_credit_recognition_coverage_accepts_direct_answer() -> None:
    issues = _find_topic_coverage_issues(
        draft=(
            "Your previous modules can be assessed for recognition, "
            "and the official review determines which credits may "
            "be transferred."
        ),
        topics=[
            {
                "topic_id": "credit_recognition",
            }
        ],
        original_email=INTERNATIONAL_BUSINESS_TRANSFER_EMAIL,
    )

    assert issues == []


def test_credit_recognition_coverage_accepts_safe_uncertainty() -> None:
    issues = _find_topic_coverage_issues(
        draft=(
            "Credit recognition for your completed modules could not "
            "be confirmed from the available official sources."
        ),
        topics=[
            {
                "topic_id": "credit_recognition",
            }
        ],
        original_email=INTERNATIONAL_BUSINESS_TRANSFER_EMAIL,
    )

    assert issues == []


def test_credit_recognition_coverage_flags_missing_answer() -> None:
    issues = _find_topic_coverage_issues(
        draft=(
            "You should apply through the appropriate application "
            "portal and submit the required documents."
        ),
        topics=[
            {
                "topic_id": "credit_recognition",
            }
        ],
        original_email=INTERNATIONAL_BUSINESS_TRANSFER_EMAIL,
    )

    assert issues == [
        (
            "topic_not_answered: credit_recognition was detected "
            "but credit transfer/recognition was not directly answered"
        )
    ]


def test_credit_recognition_query_targets_higher_semester_transfer() -> None:
    query = build_evidence_query(
        "credit_recognition",
        "Can previous university credits be recognised or transferred?",
        {
            "target_program": "Computer Engineering",
        },
    )

    assert "higher subject semester" in query
    assert "changing university" in query
    assert "second-degree programme guidance only as backup" in query


def test_credit_recognition_prefers_changing_university_evidence() -> None:
    documents = [
        {
            "title": "Second degree programme",
            "url": (
                "https://www.htw-berlin.de/en/studies/applications/"
                "special-cases/second-degree-programme/"
            ),
            "content": (
                "Previous modules from your first degree can be accredited "
                "and you may be placed in a certain subject semester."
            ),
        },
        {
            "title": "Required documents",
            "url": (
                "https://www.htw-berlin.de/en/studies/applications/"
                "special-cases/changing-study-programme-or-university/"
                "required-documents/"
            ),
            "content": (
                "When changing university, previous subject semesters and "
                "completed modules are considered for a higher semester."
            ),
        },
    ]

    ranked = filter_docs_for_programme(
        documents,
        {
            "target_program": "Computer Engineering",
        },
        topic_id="credit_recognition",
        min_keep=2,
    )

    assert ranked[0]["title"] == "Required documents"
    assert all(
        document["title"] != "Second degree programme"
        for document in ranked
    )


def test_credit_recognition_keeps_second_degree_as_safe_fallback() -> None:
    documents = [
        {
            "title": "Second degree programme",
            "url": (
                "https://www.htw-berlin.de/en/studies/applications/"
                "special-cases/second-degree-programme/"
            ),
            "content": (
                "Previous modules from your first degree can be accredited "
                "and you may be placed in a certain subject semester."
            ),
        },
    ]

    ranked = filter_docs_for_programme(
        documents,
        {
            "target_program": "Computer Engineering",
        },
        topic_id="credit_recognition",
        min_keep=1,
    )

    assert len(ranked) == 1
    assert ranked[0]["title"] == "Second degree programme"

def test_credit_scope_guidance_protects_international_applicant() -> None:
    guidance = _build_credit_geographic_scope_guidance(
        topics=[
            {
                "topic_id": "credit_recognition",
            }
        ],
        email_context={
            "country": "Morocco",
        },
        documents=[
            {
                "title": "Changing study programme or university",
                "content": (
                    "If you have previously been or are currently "
                    "enrolled at another German university, HTW Berlin "
                    "will assess previous modules and examinations."
                ),
            }
        ],
    )

    assert "outside Germany (Morocco)" in guidance
    assert "another German university" in guidance
    assert "Do not state" in guidance
    assert "applicability cannot be confirmed" in guidance


def test_credit_scope_guidance_not_needed_for_german_previous_study() -> None:
    guidance = _build_credit_geographic_scope_guidance(
        topics=[
            {
                "topic_id": "credit_recognition",
            }
        ],
        email_context={
            "country": "Germany",
        },
        documents=[
            {
                "title": "Changing study programme or university",
                "content": (
                    "Applicants from another German university may "
                    "apply for recognition of previous modules."
                ),
            }
        ],
    )

    assert guidance == ""


def test_credit_scope_guidance_not_added_without_german_only_source() -> None:
    guidance = _build_credit_geographic_scope_guidance(
        topics=[
            {
                "topic_id": "credit_recognition",
            }
        ],
        email_context={
            "country": "Morocco",
        },
        documents=[
            {
                "title": "Recognition of credits",
                "content": (
                    "Previous modules may be assessed individually."
                ),
            }
        ],
    )

    assert guidance == ""

