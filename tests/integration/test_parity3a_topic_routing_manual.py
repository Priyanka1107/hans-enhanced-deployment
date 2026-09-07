from app.email.multitopic import detect_topics
from app.email.thread_memory import classify_followup_email


def topic_ids(text, context=None):
    topics = detect_topics(
        text,
        context or {},
        max_topics=6,
    )
    return [
        item.get("topic_id")
        for item in topics
    ]


# Q8A: natural language-of-instruction wording.
q8a = """
Hello,

I am interested in the Master's programme in Project
Management and Data Science.

Is the teaching language English?

Kind regards,
Nina
""".strip()

q8a_topics = topic_ids(
    q8a,
    {
        "target_program":
            "Project Management and Data Science",
        "programme_mentioned":
            "Project Management and Data Science",
    },
)

assert "language_of_instruction" in q8a_topics, (
    "Q8A regression: 'teaching language' was not "
    f"detected as language_of_instruction: {q8a_topics}"
)

assert "application_process" not in q8a_topics, (
    "Q8A regression: generic application_process "
    f"fallback survived: {q8a_topics}"
)

print(
    "PASS: teaching-language wording maps to "
    "language_of_instruction."
)


# Q8B: required-documents detector itself must remain precise.
q8b = "And what documents do I need to apply?"

q8b_topics = topic_ids(
    q8b,
    {
        "target_program":
            "Project Management and Data Science",
        "programme_mentioned":
            "Project Management and Data Science",
    },
)

assert q8b_topics == ["required_documents"], (
    "Q8B regression: expected only required_documents, "
    f"got {q8b_topics}"
)

print(
    "PASS: follow-up-style document wording maps to "
    "required_documents."
)


# Q10 documents the existing classifier bug.
# Do NOT make it pass yet; that is Parity 3A-3.
q10 = """
Hello,

I am currently finalizing my application via Uni-Assist
for the upcoming winter semester.

I am confused about the document submission deadlines and
whether hard copies need to be sent by post or digital
uploads are sufficient.

Could you also confirm whether certified translations of
all academic transcripts are required at this stage, or
only upon admission?
""".strip()

q10_topics = topic_ids(q10)

expected_q10_topics = {
    "application_route",
    "application_deadline",
    "hard_copy_documents",
    "certified_translations",
}

assert expected_q10_topics.issubset(set(q10_topics)), (
    "Q10 topic regression: expected topics are missing. "
    f"Got {q10_topics}"
)

print(
    "PASS: Q10 substantive topics are detected correctly."
)

print()
print("Q10 current follow-up classification:")
print(
    classify_followup_email(
        q10,
        has_thread_memory=False,
    )
)

# ---------------------------------------------------------------------
# Q10 follow-up classification safety
# ---------------------------------------------------------------------

q10_no_memory = classify_followup_email(
    q10,
    has_thread_memory=False,
)

assert q10_no_memory == "new_enquiry", (
    "Q10 regression: an ordinary first enquiry containing "
    f"'I am confused' was classified as {q10_no_memory!r}"
)

print(
    "PASS: first-enquiry confusion wording remains a new enquiry."
)


q10_with_memory = classify_followup_email(
    q10,
    has_thread_memory=True,
)

assert q10_with_memory == "clarification_or_complaint", (
    "Q10 safety regression: confusion wording in an existing "
    f"thread was classified as {q10_with_memory!r}"
)

print(
    "PASS: confusion wording with thread memory still receives review."
)


explicit_previous_answer = (
    "I am confused about your previous answer regarding "
    "the application deadline."
)

explicit_previous_answer_result = classify_followup_email(
    explicit_previous_answer,
    has_thread_memory=False,
)

assert (
    explicit_previous_answer_result
    == "clarification_or_complaint"
), (
    "Follow-up safety regression: explicit reference to a "
    "previous answer was not routed to review. Got "
    f"{explicit_previous_answer_result!r}"
)

print(
    "PASS: explicit previous-answer confusion still receives review."
)


still_confused = classify_followup_email(
    "I am still confused about the deadline.",
    has_thread_memory=False,
)

assert still_confused == "clarification_or_complaint", (
    "Follow-up safety regression: 'still confused' must remain "
    f"a strong clarification signal. Got {still_confused!r}"
)

print(
    "PASS: 'still confused' remains a strong review signal."
)
