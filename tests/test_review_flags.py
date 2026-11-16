from app.email.review_flags import build_manual_verification_reasons


def test_flags_referenced_attachment_for_manual_verification() -> None:
    reasons = build_manual_verification_reasons(
        email_text=(
            "I have attached my latest transcript for your review."
        ),
        email_context={},
    )

    assert reasons == [
        (
            "Manual verification required: the enquiry refers to "
            "an attachment or supporting document that HANS has "
            "not inspected."
        )
    ]


def test_flags_ambiguous_programme_degree() -> None:
    reasons = build_manual_verification_reasons(
        email_text="I am interested in International Business.",
        email_context={
            "catalog_degree_ambiguous": True,
        },
    )

    assert reasons == [
        (
            "Manual verification required: the programme degree "
            "level is ambiguous; staff should confirm the "
            "applicable Bachelor/Master route."
        )
    ]


def test_combines_independent_manual_verification_reasons() -> None:
    reasons = build_manual_verification_reasons(
        email_text="Please see the attached transcript.",
        email_context={
            "catalog_degree_ambiguous": True,
        },
    )

    assert len(reasons) == 2


def test_returns_no_extra_reason_for_simple_supported_case() -> None:
    reasons = build_manual_verification_reasons(
        email_text="What is the application deadline?",
        email_context={},
    )

    assert reasons == []
