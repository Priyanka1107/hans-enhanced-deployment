from app.knowledge import programme_official_evidence as evidence


def test_completed_degree_prerequisite_is_relevant_to_before_graduation() -> None:
    context = {
        "target_program": "Example Master Programme",
        "target_degree": "Master",
        "catalog_degree": "Master",
        "programme_id": "example-master--master",
    }

    page = {
        "programme_ids": ["example-master--master"],
        "program_names": ["Example Master Programme"],
        "programme_id": "example-master--master",
        "program_name": "Example Master Programme",
        "degree": "Master",
        "url": "https://example.htw-berlin.de/applying",
        "final_url": "https://example.htw-berlin.de/applying",
        "title": "Applying",
        "text": (
            "Do I qualify? "
            "Applicants need a bachelor degree with at least 180 ECTS. "
            "At least one year of qualified professional experience "
            "after acquiring the bachelor's degree is required. "
            "Required documents include a copy of the degree certificate. "
            "Evidence of professional experience after the first "
            "university degree must also be submitted."
        ),
    }

    score = evidence._page_score(
        page,
        "application_before_graduation",
        context,
    )

    assert score > 0

    snippet = evidence._find_best_snippet(
        page["text"],
        evidence._topic_terms(
            "application_before_graduation"
        ),
        topic_id="application_before_graduation",
    )

    assert snippet
    assert "bachelor degree" in snippet.lower()
    assert "after acquiring" in snippet.lower()
