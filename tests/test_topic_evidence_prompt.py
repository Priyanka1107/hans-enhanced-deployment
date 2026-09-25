from app.runtime.local_llm import build_email_user_prompt


def test_prompt_renders_topic_specific_evidence_ownership():
    prompt = build_email_user_prompt(
        original_email="Please tell me the deadline and required documents.",
        email_context={
            "input_language": "en",
            "reply_language": "en",
        },
        topics=[
            {
                "topic_id": "application_deadline",
                "label": "Application deadline",
                "query": "What is the application deadline?",
            },
            {
                "topic_id": "required_documents",
                "label": "Required documents",
                "query": "Which documents are required?",
            },
        ],
        documents=[
            {
                "id": "doc-a",
                "title": "Applying",
                "content": "Deadline information",
            },
            {
                "id": "doc-b",
                "title": "Documents",
                "content": "Required documents information",
            },
        ],
        topic_evidence=[
            {
                "topic_id": "application_deadline",
                "label": "Application deadline",
                "doc_numbers": [1],
            },
            {
                "topic_id": "required_documents",
                "label": "Required documents",
                "doc_numbers": [2, 1],
            },
        ],
    )

    assert "TOPIC-SPECIFIC EVIDENCE" in prompt
    assert "- Application deadline: [Doc 1]" in prompt
    assert "- Required documents: [Doc 2], [Doc 1]" in prompt


def test_prompt_remains_backward_compatible_without_topic_evidence():
    prompt = build_email_user_prompt(
        original_email="What is the application deadline?",
        email_context={
            "input_language": "en",
            "reply_language": "en",
        },
        topics=[
            {
                "topic_id": "application_deadline",
                "label": "Application deadline",
                "query": "What is the application deadline?",
            },
        ],
        documents=[
            {
                "id": "doc-a",
                "title": "Applying",
                "content": "Deadline information",
            },
        ],
    )

    assert "TOPIC-SPECIFIC EVIDENCE" not in prompt
    assert "[Doc 1]" in prompt



def test_prompt_explicitly_limits_generation_to_detected_topics():
    prompt = build_email_user_prompt(
        original_email=(
            "Which documents do I need to submit "
            "with my application?"
        ),
        email_context={
            "input_language": "en",
            "reply_language": "en",
        },
        topics=[
            {
                "topic_id": "required_documents",
                "label": "Required documents",
                "query": "Which documents are required?",
            },
        ],
        documents=[
            {
                "id": "broad-programme-page",
                "title": "Programme and application information",
                "content": (
                    "Required documents include a degree certificate "
                    "and proof of English proficiency. "
                    "The programme is two years long. "
                    "The curriculum covers project management "
                    "and data science."
                ),
            },
        ],
        topic_evidence=[
            {
                "topic_id": "required_documents",
                "label": "Required documents",
                "doc_numbers": [1],
            },
        ],
    )

    assert (
        "Answer only the topics listed under "
        "TOPICS THAT MUST BE ANSWERED."
        in prompt
    )

    assert (
        "Evidence documents may contain information about "
        "other topics."
        in prompt
    )

    assert (
        "Do not add separate programme-duration, curriculum, "
        "language-of-instruction, study-format, admission-requirements, "
        "scholarship, or application-route information unless that "
        "topic is listed."
        in prompt
    )

    assert (
        "For required_documents, document requirements and their "
        "directly necessary qualifiers are allowed."
        in prompt
    )


def test_prompt_guards_unconfirmed_programme_framing():
    prompt = build_email_user_prompt(
        original_email=(
            "I want to apply for the English-taught Bachelor?s in Business "
            "and need to know whether I apply as EU or international."
        ),
        email_context={
            "reply_language": "en",
            "requested_language": "en",
            "target_degree": "Bachelor",
            "programme_status": "not_provided",
            "citizenship_group": "EU/EEA",
            "residence_country": "Morocco",
        },
        topics=[
            {
                "topic_id": "application_route",
                "label": "Application route / uni-assist",
                "query": "Which application route should the applicant use?",
            },
        ],
        documents=[
            {
                "id": "route-doc",
                "title": "Bachelor",
                "content": "EU/EEA application route information.",
            },
        ],
        topic_evidence=[
            {
                "topic_id": "application_route",
                "label": "Application route / uni-assist",
                "doc_numbers": [1],
            },
        ],
    )

    assert (
        "No confirmed HTW programme has been identified."
        in prompt
    )
    assert (
        "Do not present descriptive wording from the student's email "
        "as an official or confirmed programme title."
        in prompt
    )


def test_prompt_explicitly_forbids_unasked_application_deadlines():
    prompt = build_email_user_prompt(
        original_email=(
            "Should I apply as an EU applicant, and how is my "
            "French school qualification recognised?"
        ),
        email_context={
            "reply_language": "en",
            "requested_language": "en",
            "target_degree": "Bachelor",
            "programme_status": "not_provided",
            "citizenship_group": "EU/EEA",
        },
        topics=[
            {
                "topic_id": "application_route",
                "label": "Application route / uni-assist",
                "query": "Which application route should the applicant use?",
            },
            {
                "topic_id": "qualification_recognition",
                "label": "Qualification recognition",
                "query": "How is the school qualification recognised?",
            },
        ],
        documents=[
            {
                "id": "route-doc",
                "title": "Application periods",
                "content": (
                    "Application route information. "
                    "Winter deadline 30 June."
                ),
            },
            {
                "id": "recognition-doc",
                "title": "Admission requirements",
                "content": "Recognition requirements.",
            },
        ],
        topic_evidence=[
            {
                "topic_id": "application_route",
                "label": "Application route / uni-assist",
                "doc_numbers": [1],
            },
            {
                "topic_id": "qualification_recognition",
                "label": "Qualification recognition",
                "doc_numbers": [2],
            },
        ],
    )

    assert (
        "Do not add application deadlines or application periods "
        "unless application_deadline is a listed topic."
        in prompt
    )
