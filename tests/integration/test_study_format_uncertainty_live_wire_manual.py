from app.email.service import (
    _apply_study_format_uncertainty_fallback_to_draft,
)


BASE_DRAFT = """Dear Arjun,

Thank you for your interest in the programme.

Regarding the application deadline, the next application period starts later this year [Doc 1].

Regarding the study format, the programme is a full-time programme with a duration of four semesters [Doc 2].

Regarding the required documents, please prepare the requested application documents [Doc 3].

Kind regards,
HTW Berlin Student Services
"""


INSUFFICIENT_DELIVERY_EVIDENCE = [
    {
        "title": "Applying",
        "content": "Information about the application period.",
    },
    {
        "title": "Project Management and Data Science",
        "content": (
            "The programme is full-time and has a duration "
            "of four semesters. Teaching takes place at "
            "Treskowallee Campus."
        ),
    },
    {
        "title": "Required documents",
        "content": "Application documents are listed here.",
    },
]


DIRECT_ON_CAMPUS_EVIDENCE = [
    {
        "title": "Project Management and Data Science",
        "content": (
            "The programme is full-time. "
            "The programme is delivered entirely on-campus."
        ),
    },
]


def assert_contains(text, expected, name):
    if expected not in text:
        raise AssertionError(
            f"{name}: expected text not found:\n{expected}"
        )


result = _apply_study_format_uncertainty_fallback_to_draft(
    draft=BASE_DRAFT,
    email_text="Is the programme online or on-campus?",
    documents=INSUFFICIENT_DELIVERY_EVIDENCE,
    language="en",
)

assert_contains(
    result,
    (
        "Regarding the study format, the programme is a "
        "full-time programme with a duration of four "
        "semesters [Doc 2]."
    ),
    "existing supported study-format content is preserved",
)

assert_contains(
    result,
    (
        "The available official evidence does not directly "
        "confirm whether the programme is entirely online "
        "or on-campus."
    ),
    "explicit evidence-aware uncertainty is added",
)

assert_contains(
    result,
    (
        "Regarding the required documents, please prepare "
        "the requested application documents [Doc 3]."
    ),
    "later non-study-format content is preserved",
)

lowered = result.lower()

if "programme is taught on-campus" in lowered:
    raise AssertionError(
        "Fallback must not invent categorical on-campus delivery."
    )

print(
    "PASS: insufficient delivery evidence adds safe "
    "uncertainty without dropping existing content."
)


direct_result = (
    _apply_study_format_uncertainty_fallback_to_draft(
        draft=BASE_DRAFT,
        email_text="Is the programme online or on-campus?",
        documents=DIRECT_ON_CAMPUS_EVIDENCE,
        language="en",
    )
)

if direct_result != BASE_DRAFT:
    raise AssertionError(
        "Direct delivery-mode evidence must not trigger "
        "the uncertainty fallback."
    )

print(
    "PASS: direct on-campus evidence does not trigger "
    "uncertainty fallback."
)


part_time_result = (
    _apply_study_format_uncertainty_fallback_to_draft(
        draft=BASE_DRAFT,
        email_text="Is the programme full-time or part-time?",
        documents=INSUFFICIENT_DELIVERY_EVIDENCE,
        language="en",
    )
)

if part_time_result != BASE_DRAFT:
    raise AssertionError(
        "Online/on-campus uncertainty fallback must not "
        "run for full-time-vs-part-time questions."
    )

print(
    "PASS: full-time-vs-part-time question remains unchanged."
)


already_safe_draft = (
    BASE_DRAFT.replace(
        "\n\nRegarding the required documents",
        (
            "\n\nThe available official evidence does not "
            "directly confirm whether the programme is "
            "entirely online or on-campus."
            "\n\nRegarding the required documents"
        ),
    )
)

duplicate_result = (
    _apply_study_format_uncertainty_fallback_to_draft(
        draft=already_safe_draft,
        email_text="Is the programme online or on-campus?",
        documents=INSUFFICIENT_DELIVERY_EVIDENCE,
        language="en",
    )
)

if duplicate_result != already_safe_draft:
    raise AssertionError(
        "Existing uncertainty statement must not be duplicated."
    )

print(
    "PASS: existing uncertainty statement is not duplicated."
)

print()
print(
    "STUDY-FORMAT UNCERTAINTY LIVE-WIRE "
    "REGRESSION PASSED."
)
