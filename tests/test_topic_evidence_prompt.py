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
