from app.email.multitopic import (
    _is_wrong_document_for_topic,
    assess_email_quality,
)


def test_post_degree_prerequisite_is_valid_before_graduation_evidence() -> None:
    document = {
        "title": "Applying",
        "url": "https://example.htw-berlin.de/applying",
        "object_type": "official_programme_page_cache",
        "content": (
            "To be considered for the Master's programme you need "
            "a bachelor degree with at least 180 ECTS. "
            "At least one year of qualified professional experience "
            "after acquiring your bachelor's degree is required. "
            "Evidence of professional experience after the first "
            "university degree must be submitted."
        ),
    }

    assert not _is_wrong_document_for_topic(
        document,
        "application_before_graduation",
    )


def test_quality_flags_explicit_uncertainty_wording() -> None:
    draft = (
        "Dear applicant,\n\n"
        "The available official sources do not provide specific information "
        "on whether provisional transcripts are accepted. "
        "The specific policy is not detailed in the provided evidence [Doc 1].\n\n"
        "Kind regards,\n"
        "HTW Berlin Student Services"
    )

    result = assess_email_quality(
        context={
            "target_program": "Example Master Programme",
            "target_program_match_score": "1.0",
            "target_degree": "Master",
        },
        topics=[
            {
                "topic_id": "application_before_graduation",
                "label": "Application before graduation",
            }
        ],
        docs=[
            {
                "title": "Applying",
                "url": "https://example.htw-berlin.de/applying",
                "content": "Programme application information.",
                "object_type": "official_programme_page_cache",
            }
        ],
        draft=draft,
        validation={
            "is_grounded": True,
            "citations_valid": True,
            "confidence": 1.0,
        },
        original_email="Can I apply before graduation?",
    )

    assert (
        "One or more requested topics remain unresolved"
        in result["review_reason"]
    )
    assert result["quality_score"] <= 80
