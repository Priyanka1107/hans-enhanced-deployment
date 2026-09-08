from app.email.service import _find_topic_coverage_issues


study_format_topic = [
    {
        "topic_id": "study_format",
        "label": "Study format",
    }
]


# ---------------------------------------------------------------------
# 1. Student asks specifically online vs on-campus.
# Full-time + campus LOCATION is not a direct answer.
# Online-learning components must not count either.
# ---------------------------------------------------------------------

q6_email = """
Could you please tell me whether the programme is online or on campus?
""".strip()

q6_incomplete_draft = """
As for the study format, the programme is full-time and starts every
semester. The teaching language is English, and the location is
HTW Berlin, Treskowallee Campus. The programme also includes
self-paced online learning.
""".strip()

issues = _find_topic_coverage_issues(
    q6_incomplete_draft,
    study_format_topic,
    q6_email,
)

assert any(
    issue.startswith("topic_not_answered: study_format")
    for issue in issues
), (
    "Expected study_format to remain unanswered when the student "
    "asks online vs on-campus but the draft only gives full-time, "
    "campus location, and online-learning components. "
    f"Issues: {issues}"
)

print(
    "PASS: full-time, campus location and online-learning components "
    "do not answer an online-vs-on-campus question."
)


# ---------------------------------------------------------------------
# 2. Explicit uncertainty is a valid answer when the evidence
# does not establish the requested study-format dimension.
# ---------------------------------------------------------------------

uncertain_draft = """
The available official sources do not explicitly confirm whether
the programme is fully online or on-campus.
""".strip()

issues = _find_topic_coverage_issues(
    uncertain_draft,
    study_format_topic,
    q6_email,
)

assert not any(
    issue.startswith("topic_not_answered: study_format")
    for issue in issues
), (
    "Explicit evidence-aware uncertainty should count as answering "
    f"the requested study-format dimension. Issues: {issues}"
)

print(
    "PASS: explicit evidence-aware uncertainty counts as an answer."
)


# ---------------------------------------------------------------------
# 3. A direct online/on-campus answer satisfies this dimension.
# Grounding of that claim is checked separately.
# ---------------------------------------------------------------------

direct_campus_draft = """
The programme is on-campus.
""".strip()

issues = _find_topic_coverage_issues(
    direct_campus_draft,
    study_format_topic,
    q6_email,
)

assert not any(
    issue.startswith("topic_not_answered: study_format")
    for issue in issues
), (
    "A direct on-campus answer should satisfy topic coverage. "
    f"Issues: {issues}"
)

print(
    "PASS: direct on-campus answer satisfies topic coverage."
)


# ---------------------------------------------------------------------
# 4. If the student asks full-time vs part-time, full-time IS
# a direct answer.
# ---------------------------------------------------------------------

full_time_email = """
Is the programme full-time or part-time?
""".strip()

full_time_draft = """
The programme is full-time.
""".strip()

issues = _find_topic_coverage_issues(
    full_time_draft,
    study_format_topic,
    full_time_email,
)

assert not any(
    issue.startswith("topic_not_answered: study_format")
    for issue in issues
), (
    "Full-time should answer a full-time-vs-part-time question. "
    f"Issues: {issues}"
)

print(
    "PASS: full-time directly answers a full-time-vs-part-time question."
)


# ---------------------------------------------------------------------
# 5. For a general study-format question, a substantive recognised
# study-format value such as full-time is acceptable.
# ---------------------------------------------------------------------

general_email = """
What is the study format of the programme?
""".strip()

issues = _find_topic_coverage_issues(
    full_time_draft,
    study_format_topic,
    general_email,
)

assert not any(
    issue.startswith("topic_not_answered: study_format")
    for issue in issues
), (
    "A substantive study-format value should satisfy a general "
    f"study-format question. Issues: {issues}"
)

print(
    "PASS: substantive study-format value answers a general question."
)


print()
print("PARITY 3C-1 STUDY-FORMAT COVERAGE REGRESSION PASSED.")
