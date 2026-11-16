from app.email.scope_router import classify_email_scope


def test_routes_supported_admissions_question_to_hans() -> None:
    decision = classify_email_scope(
        subject="Application question",
        email_text=(
            "What is the application deadline for the "
            "International Business programme?"
        ),
    )

    assert decision.route == "HANS"


def test_routes_clear_mensa_question_to_skip() -> None:
    decision = classify_email_scope(
        subject="Mensa",
        email_text="What is today's Mensa lunch menu?",
    )

    assert decision.route == "SKIP"


def test_hans_signal_takes_priority_over_out_of_scope_word() -> None:
    decision = classify_email_scope(
        subject="Application",
        email_text=(
            "I have an admission question and also want to know "
            "where the Mensa is."
        ),
    )

    assert decision.route == "HANS"


def test_uncertain_message_is_sent_to_manual_review() -> None:
    decision = classify_email_scope(
        subject="General question",
        email_text="Could someone please contact me?",
    )

    assert decision.route == "REVIEW"


def test_routes_proof_of_english_question_to_hans() -> None:
    decision = classify_email_scope(
        email_text="Is proof of English required?",
    )

    assert decision.route == "HANS"


def test_routes_required_documents_question_to_hans() -> None:
    decision = classify_email_scope(
        email_text="Which documents are required?",
    )

    assert decision.route == "HANS"
