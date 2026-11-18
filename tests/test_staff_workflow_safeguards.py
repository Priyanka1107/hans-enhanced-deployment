from __future__ import annotations

from app.email.review_flags import build_manual_verification_reasons
from app.email.scope_router import classify_email_scope
from app.email.service import (
    _find_audience_issues,
    _find_source_applicability_issues,
    _find_topic_coverage_issues,
)
from enhanced_email_ui import EnhancedHANSEmailUI


def test_attachment_enquiry_always_requires_manual_verification():
    reasons = build_manual_verification_reasons(
        email_text=(
            "Please check the attached transcript and confirm "
            "whether I can enter the third semester."
        ),
        email_context={},
    )

    assert any(
        "attachment" in reason.lower()
        and "has not inspected" in reason.lower()
        for reason in reasons
    )


def test_out_of_scope_cafeteria_question_is_not_sent_to_generation():
    decision = classify_email_scope(
        subject="Mensa",
        email_text="What is today's lunch menu?",
    )

    assert decision.route == "SKIP"


def test_unclear_general_request_is_held_for_manual_review():
    decision = classify_email_scope(
        subject="Question",
        email_text="Please contact me about my situation.",
    )

    assert decision.route == "REVIEW"


def test_supported_admissions_question_is_sent_to_hans():
    decision = classify_email_scope(
        subject="Application",
        email_text=(
            "What is the application deadline for a Bachelor's "
            "programme at HTW Berlin?"
        ),
    )

    assert decision.route == "HANS"


def test_staff_reply_must_not_speak_as_if_hans_is_the_applicant():
    draft = (
        "Dear applicant,\n\n"
        "I want to apply to HTW Berlin and would like to submit "
        "my documents next week.\n\n"
        "Kind regards,\nHTW Berlin Student Services"
    )

    assert _find_audience_issues(draft)


def test_valid_staff_confirmation_is_not_flagged_as_role_reversal():
    draft = (
        "Dear applicant,\n\n"
        "I can confirm that the programme page lists the "
        "application route described below.\n\n"
        "Kind regards,\nHTW Berlin Student Services"
    )

    assert _find_audience_issues(draft) == []


def test_late_language_certificate_question_must_be_answered_directly():
    email = (
        "Can I submit my English certificate later, after the "
        "application deadline or upon conditional acceptance?"
    )
    topics = [
        {
            "topic_id": "english_language_requirements",
            "label": "English language requirements",
        }
    ]
    draft = (
        "The programme page does not list an English language "
        "proof requirement."
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


def test_source_applicability_is_flagged_when_only_generic_evidence_exists():
    topics = [
        {
            "topic_id": "qualification_recognition",
            "label": "Qualification recognition",
            "official_source_count": 0,
            "retrieved_source_count": 4,
            "source_count": 2,
        }
    ]

    issues = _find_source_applicability_issues(
        topics
    )

    assert any(
        issue.startswith("source_applicability_review:")
        for issue in issues
    )


def test_programme_specific_official_evidence_clears_source_applicability_flag():
    topics = [
        {
            "topic_id": "qualification_recognition",
            "label": "Qualification recognition",
            "official_source_count": 1,
            "retrieved_source_count": 4,
            "source_count": 2,
        }
    ]

    assert _find_source_applicability_issues(
        topics
    ) == []


def test_common_document_attachments_are_viewable_but_executables_are_blocked():
    message = {
        "attachments": [
            {"filename": "transcript.pdf"},
            {"filename": "certificate.docx"},
            {"filename": "results.xlsx"},
            {"filename": "passport.png"},
            {"filename": "installer.exe"},
            {"filename": "macro.docm"},
        ]
    }

    supported = EnhancedHANSEmailUI._supported_attachments(
        message
    )

    names = [
        item[1]["filename"]
        for item in supported
    ]

    assert "transcript.pdf" in names
    assert "certificate.docx" in names
    assert "results.xlsx" in names
    assert "passport.png" in names
    assert "installer.exe" not in names
    assert "macro.docm" not in names
