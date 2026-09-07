from datetime import date

from app.email.deadline_temporal import (
    determine_application_timeline,
)


evidence = """
Important dates
Next intakes

Winter Semester 26/27
Start of studies: 1 October 2026
Application period closed

Summer Semester 27
Start of studies: 1 April 2027
Application period: 1 May to 31 August 2026

Winter Semester 27/28
Start of studies: 1 October 2027
Application period: 1 November 2026 to 28 February 2027

Summer Semester 28
Start of studies: 1 April 2028
Application period: 1 May to 31 August 2027
"""


timeline = determine_application_timeline(
    evidence,
    as_of_date=date(
        2026,
        9,
        7,
    ),
)


periods = timeline["periods"]

assert len(periods) == 4, (
    f"Expected 4 application periods, got {len(periods)}"
)


statuses = {
    period["label"].lower():
        period["status"]
    for period in periods
}

assert statuses[
    "winter semester 26/27"
] == "closed"

assert statuses[
    "summer semester 27"
] == "closed"

assert statuses[
    "winter semester 27/28"
] == "future"

assert statuses[
    "summer semester 28"
] == "future"

print(
    "PASS: past and future MPMD periods "
    "are classified correctly."
)


assert timeline["current_period"] is None, (
    "No regular application period should be open "
    "on 2026-09-07."
)

print(
    "PASS: no application period is incorrectly "
    "classified as currently open."
)


next_period = timeline["next_period"]

assert next_period is not None

assert (
    next_period["label"].lower()
    == "winter semester 27/28"
)

assert (
    next_period["application_start"]
    == date(2026, 11, 1)
)

assert (
    next_period["application_end"]
    == date(2027, 2, 28)
)

print(
    "PASS: next regular application period is "
    "Winter Semester 27/28."
)


# Boundary safety: the final day is still inside
# the application period.
summer_end = determine_application_timeline(
    evidence,
    as_of_date=date(
        2026,
        8,
        31,
    ),
)

assert (
    summer_end["current_period"] is not None
)

assert (
    summer_end["current_period"]["label"].lower()
    == "summer semester 27"
)

assert (
    summer_end["current_period"]["status"]
    == "open"
)

print(
    "PASS: application-period end date remains open."
)


# One day later it must be closed.
after_summer = determine_application_timeline(
    evidence,
    as_of_date=date(
        2026,
        9,
        1,
    ),
)

assert (
    after_summer["current_period"] is None
)

assert (
    after_summer["next_period"]["label"].lower()
    == "winter semester 27/28"
)

print(
    "PASS: period closes immediately after its end date."
)


print()
print("PARITY 3B-1A TEMPORAL CLASSIFIER PASSED.")

# ---------------------------------------------------------------------
# Service temporal-guidance integration
# ---------------------------------------------------------------------

from app.email.service import (
    _build_programme_deadline_temporal_guidance,
)


deadline_document = {
    "id": (
        "official_programme_page::"
        "Project Management and Data Science::"
        "https://mpmd.htw-berlin.de/applying::"
        "application_deadline"
    ),
    "title": (
        "Applying - Project Management and "
        "Data Science Master - HTW Berlin"
    ),
    "source_url": "https://mpmd.htw-berlin.de/applying",
    "url": "https://mpmd.htw-berlin.de/applying",
    "object_type": "official_programme_page_cache",
    "metadata": {
        "topic_id": "application_deadline",
    },
    "content": evidence,
}


deadline_guidance = (
    _build_programme_deadline_temporal_guidance(
        topics=[
            {
                "topic_id": "application_deadline",
            }
        ],
        email_context={
            "programme_status": "confirmed",
            "target_program":
                "Project Management and Data Science",
        },
        documents=[
            deadline_document,
        ],
        as_of_date=date(
            2026,
            9,
            7,
        ),
    )
)

assert deadline_guidance, (
    "Expected temporal guidance for a confirmed "
    "programme deadline enquiry."
)

assert (
    "No regular application period is currently open"
    in deadline_guidance
)

assert (
    "Winter Semester 27/28"
    in deadline_guidance
)

assert "2026-11-01" in deadline_guidance
assert "2027-02-28" in deadline_guidance

assert (
    "Summer Semester 27"
    in deadline_guidance
    and "closed" in deadline_guidance
)

print(
    "PASS: service guidance identifies closed/current/"
    "next programme periods."
)


# Q3 safety: required-documents-only questions must not
# activate deadline temporal guidance.
documents_only_guidance = (
    _build_programme_deadline_temporal_guidance(
        topics=[
            {
                "topic_id": "required_documents",
            }
        ],
        email_context={
            "programme_status": "confirmed",
            "target_program":
                "Project Management and Data Science",
        },
        documents=[
            deadline_document,
        ],
        as_of_date=date(
            2026,
            9,
            7,
        ),
    )
)

assert documents_only_guidance == "", (
    "Q3 regression: temporal deadline guidance leaked "
    "into a required-documents-only enquiry."
)

print(
    "PASS: required-documents-only enquiry does not "
    "activate deadline guidance."
)


# Programme-specific temporal logic must not be applied when
# programme resolution is absent.
unresolved_guidance = (
    _build_programme_deadline_temporal_guidance(
        topics=[
            {
                "topic_id": "application_deadline",
            }
        ],
        email_context={
            "programme_status": "not_provided",
        },
        documents=[
            deadline_document,
        ],
        as_of_date=date(
            2026,
            9,
            7,
        ),
    )
)

assert unresolved_guidance == "", (
    "Programme-specific temporal guidance was applied "
    "without a confirmed programme."
)

print(
    "PASS: programme temporal guidance requires "
    "confirmed programme context."
)

# ---------------------------------------------------------------------
# Post-generation programme deadline safeguard
# ---------------------------------------------------------------------

from app.email.service import (
    _apply_programme_deadline_temporal_safeguard,
)


q6_bad_draft = """
Dear Arjun,

Thank you for your interest in the Master's programme in Project Management and Data Science at HTW Berlin.

Regarding the application deadline, according to our official website [Doc 1], we are currently accepting applications for the International Master's in Project Management and Data Science (MPMD) for Intake summer semester 2027 (start of studies: 1 April 2027). The application period is from 1 May to 31 August 2026.

As for the required documents, please refer to our official programme page [Doc 2] which lists the necessary documents for the application.

Regarding English language requirements, we accept TOEFL, IELTS and other recognised evidence [Doc 2].

As for the study format, the programme is full-time at HTW Berlin [Doc 3].

Kind regards,
HTW Berlin Student Services
""".strip()


corrected_q6 = (
    _apply_programme_deadline_temporal_safeguard(
        draft=q6_bad_draft,
        topics=[
            {"topic_id": "application_deadline"},
            {"topic_id": "required_documents"},
            {"topic_id": "english_language_requirements"},
            {"topic_id": "study_format"},
        ],
        email_context={
            "programme_status": "confirmed",
            "target_program":
                "Project Management and Data Science",
        },
        documents=[
            deadline_document,
        ],
        as_of_date=date(
            2026,
            9,
            7,
        ),
    )
)


assert "currently accepting applications" not in (
    corrected_q6.lower()
)

assert "1 May to 31 August 2026" not in corrected_q6

assert "Winter Semester 27/28" in corrected_q6
assert "1 November 2026" in corrected_q6
assert "28 February 2027" in corrected_q6
assert "[Doc 1]" in corrected_q6

print(
    "PASS: stale Q6 deadline paragraph is "
    "deterministically corrected."
)


# Other requested topics must remain untouched.
assert (
    "As for the required documents"
    in corrected_q6
)

assert (
    "Regarding English language requirements"
    in corrected_q6
)

assert (
    "As for the study format"
    in corrected_q6
)

print(
    "PASS: deadline correction preserves "
    "non-deadline answer sections."
)


# Q3 safety: without application_deadline, draft must not change.
q3_draft = """
Dear Daniel,

To apply, please prepare the required documents listed
on the official programme page [Doc 1].

Kind regards,
HTW Berlin Student Services
""".strip()

q3_after = (
    _apply_programme_deadline_temporal_safeguard(
        draft=q3_draft,
        topics=[
            {"topic_id": "required_documents"},
        ],
        email_context={
            "programme_status": "confirmed",
            "target_program":
                "Project Management and Data Science",
        },
        documents=[
            deadline_document,
        ],
        as_of_date=date(
            2026,
            9,
            7,
        ),
    )
)

assert q3_after == q3_draft

print(
    "PASS: deadline safeguard does not alter "
    "required-documents-only drafts."
)
