from app.email import service


def test_post_degree_before_graduation_safeguard_inserts_documented_requirement() -> None:
    safeguard = getattr(
        service,
        "_apply_before_graduation_post_degree_safeguard",
        None,
    )

    assert callable(safeguard)

    draft = (
        "Dear applicant,\n\n"
        "The provided official sources do not specify how provisional "
        "transcripts are handled.\n\n"
        "Application deadline\n"
        "The application period is currently open [Doc 1].\n\n"
        "Kind regards,\n"
        "HTW Berlin Student Services"
    )

    result = safeguard(
        draft=draft,
        topics=[
            {
                "topic_id": "application_before_graduation",
                "label": "Application before graduation",
            }
        ],
        email_context={
            "target_program": "Example Master Programme",
            "target_degree": "Master",
            "previous_degree": "Bachelor",
            "programme_status": "confirmed",
        },
        documents=[
            {
                "title": "Deadline",
                "object_type": "official_programme_page_cache",
                "content": "Application deadline information.",
            },
            {
                "title": "Applying",
                "object_type": "official_programme_page_cache",
                "content": (
                    "To be considered for the programme you need "
                    "a bachelor degree with at least 180 ECTS. "
                    "At least one year of qualified professional experience "
                    "after acquiring your bachelor's degree is required."
                ),
            },
        ],
        original_email=(
            "I am currently completing my final year in BBA. "
            "I will receive my final results later."
        ),
    )

    lower_result = result.lower()

    assert "at least one year" in lower_result
    assert "qualified professional experience" in lower_result
    assert "after acquiring" in lower_result
    assert "[doc 2]" in lower_result

    # Explain the documented timing consequence without issuing
    # a binding admission decision.
    assert "cannot yet have started" in lower_result
    assert "official application review" in lower_result


def test_post_degree_before_graduation_safeguard_leaves_generic_case_unchanged() -> None:
    safeguard = getattr(
        service,
        "_apply_before_graduation_post_degree_safeguard",
        None,
    )

    assert callable(safeguard)

    draft = (
        "Dear applicant,\n\n"
        "Applicants in their final semester may apply [Doc 1].\n\n"
        "Kind regards,\n"
        "HTW Berlin Student Services"
    )

    result = safeguard(
        draft=draft,
        topics=[
            {
                "topic_id": "application_before_graduation",
                "label": "Application before graduation",
            }
        ],
        email_context={
            "target_program": "Example Master Programme",
            "target_degree": "Master",
            "previous_degree": "Bachelor",
            "programme_status": "confirmed",
        },
        documents=[
            {
                "title": "Master's study programmes",
                "object_type": "web",
                "content": (
                    "Applicants currently in the final semester "
                    "may apply if their final thesis is registered."
                ),
            }
        ],
        original_email=(
            "I am currently completing my final year in BBA."
        ),
    )

    assert result == draft


def test_post_degree_safeguard_adds_timing_consequence_when_requirement_alone_exists() -> None:
    safeguard = service._apply_before_graduation_post_degree_safeguard

    draft = (
        "Dear applicant,\n\n"
        "The programme requires at least one year of qualified professional "
        "experience after acquiring your Bachelor's degree [Doc 2].\n\n"
        "Kind regards,\n"
        "HTW Berlin Student Services"
    )

    result = safeguard(
        draft=draft,
        topics=[
            {
                "topic_id": "application_before_graduation",
                "label": "Application before graduation",
            }
        ],
        email_context={
            "target_program": "Example Master Programme",
            "target_degree": "Master",
            "previous_degree": "Bachelor",
            "programme_status": "confirmed",
        },
        documents=[
            {
                "title": "Deadline",
                "object_type": "official_programme_page_cache",
                "content": "Application deadline information.",
            },
            {
                "title": "Applying",
                "object_type": "official_programme_page_cache",
                "content": (
                    "To be considered for the programme you need "
                    "a bachelor degree with at least 180 ECTS. "
                    "At least one year of qualified professional experience "
                    "after acquiring your bachelor's degree is required."
                ),
            },
        ],
        original_email=(
            "I am currently completing my final year in BBA. "
            "I will receive my final results later."
        ),
    )

    lower_result = result.lower()

    assert "cannot yet have started" in lower_result
    assert "official application review" in lower_result
