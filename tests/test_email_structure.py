from app.email.multitopic import clean_staff_draft
from app.email.service import _clean_email_structure


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
