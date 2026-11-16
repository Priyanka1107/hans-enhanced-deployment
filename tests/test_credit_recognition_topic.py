from app.email.multitopic import detect_topics
from app.email.service import _find_topic_coverage_issues


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
    assert "application_route" in topic_ids
    assert "required_documents" in topic_ids


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
