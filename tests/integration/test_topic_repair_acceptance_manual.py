from app.email.service import _is_topic_repair_safe_to_accept


original = """
Dear Arjun,

The next application period is from 1 November 2026 to
28 February 2027 [Doc 1].

The required documents are listed on the programme page [Doc 2].

Accepted English proof includes IELTS and TOEFL [Doc 3].

The programme is full-time and lasts four semesters [Doc 4].

Kind regards,
HTW Berlin Student Services
""".strip()


good_repair = """
Dear Arjun,

The next application period is from 1 November 2026 to
28 February 2027 [Doc 1].

The required documents are listed on the programme page [Doc 2].

Accepted English proof includes IELTS and TOEFL [Doc 3].

The programme is full-time and lasts four semesters [Doc 4].
The available official sources do not explicitly confirm whether
the programme is fully online or on-campus.

Kind regards,
HTW Berlin Student Services
""".strip()


drops_documents = """
Dear Arjun,

The next application period is from 1 November 2026 to
28 February 2027 [Doc 1].

Accepted English proof includes IELTS and TOEFL [Doc 3].

The available official sources do not explicitly confirm whether
the programme is fully online or on-campus.

Kind regards,
HTW Berlin Student Services
""".strip()


# ------------------------------------------------------------------
# 1. Coverage improves, no claim problems, existing content preserved.
# ------------------------------------------------------------------

accepted = _is_topic_repair_safe_to_accept(
    original_draft=original,
    repaired_draft=good_repair,
    initial_coverage_issues=[
        "topic_not_answered: study_format was detected "
        "but the requested study-format dimension "
        "was not directly answered"
    ],
    repaired_coverage_issues=[],
    original_claim_support_issues=[],
    repaired_claim_support_issues=[],
)

assert accepted is True, (
    "A repair that fixes coverage without weakening other content "
    "should be accepted."
)

print(
    "PASS: safe coverage improvement is accepted."
)


# ------------------------------------------------------------------
# 2. Coverage improves, but repair introduces unsupported claim.
# ------------------------------------------------------------------

accepted = _is_topic_repair_safe_to_accept(
    original_draft=original,
    repaired_draft=good_repair,
    initial_coverage_issues=[
        "topic_not_answered: study_format"
    ],
    repaired_coverage_issues=[],
    original_claim_support_issues=[],
    repaired_claim_support_issues=[
        "study_format: cited source does not directly support the claim"
    ],
)

assert accepted is False, (
    "A repair must not be accepted when it introduces a new "
    "claim-support problem."
)

print(
    "PASS: repair introducing claim-support problems is rejected."
)


# ------------------------------------------------------------------
# 3. Coverage improves but another answer paragraph disappears.
# ------------------------------------------------------------------

accepted = _is_topic_repair_safe_to_accept(
    original_draft=original,
    repaired_draft=drops_documents,
    initial_coverage_issues=[
        "topic_not_answered: study_format"
    ],
    repaired_coverage_issues=[],
    original_claim_support_issues=[],
    repaired_claim_support_issues=[],
)

assert accepted is False, (
    "A repair must not be accepted if it fixes study format by "
    "dropping an existing non-study-format answer."
)

print(
    "PASS: repair dropping existing answer content is rejected."
)


# ------------------------------------------------------------------
# 4. Coverage does not strictly improve.
# ------------------------------------------------------------------

accepted = _is_topic_repair_safe_to_accept(
    original_draft=original,
    repaired_draft=original,
    initial_coverage_issues=[
        "topic_not_answered: study_format"
    ],
    repaired_coverage_issues=[
        "topic_not_answered: study_format"
    ],
    original_claim_support_issues=[],
    repaired_claim_support_issues=[],
)

assert accepted is False, (
    "Repair must be rejected when the coverage issue set "
    "does not strictly improve."
)

print(
    "PASS: non-improving repair is rejected."
)


# ------------------------------------------------------------------
# 5. Existing claim issue may remain, but repair must not add a new one.
# ------------------------------------------------------------------

accepted = _is_topic_repair_safe_to_accept(
    original_draft=original,
    repaired_draft=good_repair,
    initial_coverage_issues=[
        "topic_not_answered: study_format"
    ],
    repaired_coverage_issues=[],
    original_claim_support_issues=[
        "required_documents: cited source does not directly support the claim"
    ],
    repaired_claim_support_issues=[
        "required_documents: cited source does not directly support the claim"
    ],
)

assert accepted is True, (
    "An existing independent claim issue should not block a repair "
    "when the repair does not introduce any new claim issue."
)

print(
    "PASS: unchanged pre-existing claim issue does not count as worsening."
)




# ------------------------------------------------------------------
# 6. "Online application" wording is NOT a study-format paragraph.
# A repair must not be allowed to drop required-document content
# merely because that paragraph contains the word "online".
# ------------------------------------------------------------------

original_online_application = """
Dear Arjun,

The next application period is from 1 November 2026 to
28 February 2027 [Doc 1].

The required documents are listed on our website. You can find
more information on the required documents and the online
application form on our programme page [Doc 2].

Accepted English proof includes IELTS and TOEFL [Doc 3].

The programme is full-time and lasts four semesters [Doc 4].

Kind regards,
HTW Berlin Student Services
""".strip()


repair_drops_online_application_paragraph = """
Dear Arjun,

The next application period is from 1 November 2026 to
28 February 2027 [Doc 1].

Accepted English proof includes IELTS and TOEFL [Doc 3].

The available official sources do not explicitly confirm whether
the programme is fully online or on-campus.

Kind regards,
HTW Berlin Student Services
""".strip()


accepted = _is_topic_repair_safe_to_accept(
    original_draft=original_online_application,
    repaired_draft=repair_drops_online_application_paragraph,
    initial_coverage_issues=[
        "topic_not_answered: study_format"
    ],
    repaired_coverage_issues=[],
    original_claim_support_issues=[],
    repaired_claim_support_issues=[],
)

assert accepted is False, (
    "The word 'online' in 'online application form' must not make "
    "a required-documents paragraph replaceable as study-format content."
)

print(
    "PASS: online-application wording is not treated as "
    "replaceable study-format content."
)

print()
print("PARITY 3C-2 SAFE REPAIR GATE REGRESSION PASSED.")
