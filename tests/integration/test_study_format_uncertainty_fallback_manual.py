from app.email.service import (
    _build_study_format_uncertainty_fallback,
)


def check(
    name,
    *,
    email_text,
    evidence_text,
    expected,
):
    result = _build_study_format_uncertainty_fallback(
        email_text=email_text,
        evidence_text=evidence_text,
    )

    if result != expected:
        raise AssertionError(
            f"{name}\n"
            f"EXPECTED: {expected!r}\n"
            f"GOT:      {result!r}"
        )

    print(f"PASS: {name}")


check(
    "online-vs-on-campus with insufficient evidence",
    email_text=(
        "Is the programme online or on-campus?"
    ),
    evidence_text=(
        "The programme is full-time and has a duration "
        "of four semesters. Teaching takes place at "
        "Treskowallee Campus."
    ),
    expected=(
        "The available official evidence confirms that "
        "the programme is full-time. However, it does "
        "not directly confirm whether the programme is "
        "entirely online or on-campus."
    ),
)


check(
    "direct on-campus evidence",
    email_text=(
        "Is the programme online or on-campus?"
    ),
    evidence_text=(
        "The programme is delivered entirely on-campus."
    ),
    expected=None,
)


check(
    "direct online evidence",
    email_text=(
        "Is the programme online or on-campus?"
    ),
    evidence_text=(
        "The programme is delivered entirely online."
    ),
    expected=None,
)


check(
    "full-time-vs-part-time should not use delivery fallback",
    email_text=(
        "Is the programme full-time or part-time?"
    ),
    evidence_text=(
        "The programme is full-time."
    ),
    expected=None,
)


print()
print(
    "STUDY-FORMAT UNCERTAINTY FALLBACK "
    "REGRESSION PASSED."
)
