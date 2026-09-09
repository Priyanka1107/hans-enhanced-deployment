from app.email.multitopic import clean_staff_draft
from app.email.service import (
    _clean_email_structure,
    _find_audience_issues,
)


def test_staff_cleanup_preserves_canonical_greeting_over_model_greeting():
    raw_model_draft = """Dear Admissions Team,

Thank you for your message.

Kind regards,
HTW Berlin Student Services"""

    context = {
        "student_name": None,
        "input_language": "en",
        "reply_language": "en",
    }

    after_staff_cleanup = clean_staff_draft(
        raw_model_draft,
        context,
    )

    final_draft = _clean_email_structure(
        after_staff_cleanup
    )

    assert final_draft.startswith("Dear applicant,")
    assert "Dear Admissions Team" not in final_draft
    assert final_draft.count("Dear applicant,") == 1
    assert "Thank you for your message." in final_draft
    assert final_draft.endswith(
        "Kind regards,\nHTW Berlin Student Services"
    )


def test_staff_cleanup_replaces_placeholder_signature_with_canonical_closing():
    raw_model_draft = """Dear Admissions Team,

Thank you for your enquiry.

Kind regards,
[Your Name]"""

    context = {
        "student_name": None,
        "input_language": "en",
        "reply_language": "en",
    }

    final_draft = _clean_email_structure(
        clean_staff_draft(
            raw_model_draft,
            context,
        )
    )

    assert "[Your Name]" not in final_draft
    assert final_draft.lower().count("kind regards") == 1
    assert final_draft.endswith(
        "Kind regards,\nHTW Berlin Student Services"
    )


def test_staff_cleanup_replaces_alternate_model_closing():
    raw_model_draft = """Dear Admissions Team,

Thank you for your enquiry.

Best regards,
[Your Name]"""

    context = {
        "student_name": None,
        "input_language": "en",
        "reply_language": "en",
    }

    final_draft = _clean_email_structure(
        clean_staff_draft(
            raw_model_draft,
            context,
        )
    )

    assert "Best regards" not in final_draft
    assert "[Your Name]" not in final_draft
    assert final_draft.endswith(
        "Kind regards,\nHTW Berlin Student Services"
    )


def test_staff_cleanup_keeps_already_canonical_closing_single():
    raw_model_draft = """Dear applicant,

Thank you for your enquiry.

Kind regards,
HTW Berlin Student Services"""

    context = {
        "student_name": None,
        "input_language": "en",
        "reply_language": "en",
    }

    final_draft = _clean_email_structure(
        clean_staff_draft(
            raw_model_draft,
            context,
        )
    )

    assert final_draft.lower().count("kind regards") == 1
    assert final_draft.endswith(
        "Kind regards,\nHTW Berlin Student Services"
    )


def test_audience_validator_flags_applicant_role_reversal():
    draft = """Dear applicant,

I am writing to apply for the Bachelor's in Business at HTW Berlin.
I am a dual citizen of France and Morocco.

Kind regards,
HTW Berlin Student Services"""

    issues = _find_audience_issues(draft)

    assert issues


def test_audience_validator_flags_first_person_application_intent():
    draft = """Dear applicant,

I would like to know whether my qualification is recognised.
I want to apply directly to HTW Berlin.

Kind regards,
HTW Berlin Student Services"""

    issues = _find_audience_issues(draft)

    assert issues


def test_audience_validator_allows_legitimate_staff_recommendation():
    draft = """Dear applicant,

I recommend checking the official programme page before applying.
You can then use the application route applicable to you.

Kind regards,
HTW Berlin Student Services"""

    issues = _find_audience_issues(draft)

    assert issues == []


def test_audience_validator_allows_staff_confirmation():
    draft = """Dear applicant,

I can confirm that you may apply through the route described below.
Your qualification must still meet the recognition requirements.

Kind regards,
HTW Berlin Student Services"""

    issues = _find_audience_issues(draft)

    assert issues == []
