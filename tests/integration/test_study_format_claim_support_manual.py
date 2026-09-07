from app.email.service import (
    _find_claim_support_issues,
)


supporting_doc = {
    "title": "MPMD programme page",
    "source_url": "https://mpmd.htw-berlin.de/",
    "content": (
        "The programme is full-time. "
        "The teaching language is English. "
        "Each module provides a mix of lectures, case studies, "
        "self-paced online learning, and interactive video conferences."
    ),
}


# ---------------------------------------------------------------------
# Regression 1:
# Online-learning components must NOT be interpreted as a claim
# that the whole programme is an online programme.
# ---------------------------------------------------------------------

q6_style_paragraph = """
The Master's programme in Project Management and Data Science
is taught entirely in English [Doc 1]. The programme is
full-time, and the duration is four semesters (two years)
[Doc 1]. We offer a mix of lectures, case studies,
self-paced online learning, and project work with industry
partners.
""".strip()

q6_issues = _find_claim_support_issues(
    q6_style_paragraph,
    [supporting_doc],
)

assert not any(
    issue.startswith("study_format:")
    for issue in q6_issues
), (
    "False positive: online-learning components were "
    "interpreted as a categorical online-programme claim. "
    f"Issues: {q6_issues}"
)

print(
    "PASS: online-learning components do not create "
    "a categorical study-format claim."
)


# ---------------------------------------------------------------------
# Regression 2:
# A genuine unsupported categorical online-programme claim
# must STILL be rejected.
# ---------------------------------------------------------------------

explicit_online_claim = """
The programme is online [Doc 1].
""".strip()

online_issues = _find_claim_support_issues(
    explicit_online_claim,
    [supporting_doc],
)

assert any(
    issue.startswith("study_format:")
    for issue in online_issues
), (
    "Safety regression: unsupported categorical online "
    "programme claim was not detected."
)

print(
    "PASS: unsupported explicit online-programme claim "
    "is still rejected."
)


# ---------------------------------------------------------------------
# Regression 3:
# Explicit categorical claim is valid when the cited source
# directly supports it.
# ---------------------------------------------------------------------

online_supporting_doc = {
    "title": "Programme study format",
    "source_url": "https://example.invalid/programme",
    "content": (
        "Study format: online programme. "
        "The programme is delivered fully online."
    ),
}

supported_online_issues = _find_claim_support_issues(
    explicit_online_claim,
    [online_supporting_doc],
)

assert not any(
    issue.startswith("study_format:")
    for issue in supported_online_issues
), (
    "Supported categorical online-programme claim "
    "was incorrectly rejected. "
    f"Issues: {supported_online_issues}"
)

print(
    "PASS: explicitly supported online-programme claim "
    "remains valid."
)

print()
print(
    "STUDY-FORMAT CLAIM-SUPPORT REGRESSION PASSED."
)
