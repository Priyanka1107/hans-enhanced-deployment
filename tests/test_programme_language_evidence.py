from app.knowledge import programme_official_evidence as evidence


def test_german_teaching_language_is_relevant_to_english_requirement() -> None:
    context = {
        "target_program": "Computer Engineering",
        "target_program_url": "https://ce-bachelor.htw-berlin.de/",
        "programme_id": "computer-engineering--bachelor",
        "catalog_degree": "Bachelor",
    }

    page = {
        "programme_ids": [
            "computer-engineering--bachelor",
        ],
        "program_names": [
            "Computer Engineering",
        ],
        "programme_id": "computer-engineering--bachelor",
        "program_name": "Computer Engineering",
        "degree": "Bachelor",
        "url": "https://ce-bachelor.htw-berlin.de/",
        "final_url": "https://ce-bachelor.htw-berlin.de/",
        "title": "Computer Engineering - Bachelor",
        "text": (
            "Computer Engineering - Bachelor "
            "Abschluss Bachelor of Engineering "
            "Regelstudienzeit 6 Semester "
            "Unterrichtssprache Deutsch "
            "Standort Campus Wilhelminenhof"
        ),
    }

    score = evidence._page_score(
        page,
        "english_language_requirements",
        context,
    )

    assert score > 0

    snippet = evidence._find_best_snippet(
        page["text"],
        evidence._topic_terms(
            "english_language_requirements"
        ),
        topic_id="english_language_requirements",
    )

    assert snippet
    assert "Unterrichtssprache Deutsch" in snippet

def test_bachelor_context_excludes_master_subdomain_pages() -> None:
    bachelor_context = {
        "target_program": "Computer Engineering",
        "target_program_url": "https://ce-bachelor.htw-berlin.de/",
        "programme_id": "computer-engineering--bachelor",
        "catalog_degree": "Bachelor",
        "target_degree": "Bachelor",
    }

    master_page = {
        "programme_ids": [
            "computer-engineering--master",
        ],
        "program_names": [
            "Computer Engineering",
        ],
        "degrees": [
            "Bachelor",
            "Master",
        ],
        "url": "https://ce-master.htw-berlin.de/",
        "final_url": "https://ce-master.htw-berlin.de/",
        "title": "Computer Engineering - Master",
        "text": (
            "Computer Engineering - Master "
            "Unterrichtssprache Deutsch"
        ),
    }

    assert (
        evidence._programme_matches_page(
            bachelor_context,
            master_page,
        )
        is False
    )

def test_ambiguous_degree_excludes_different_programme_subpage() -> None:
    ambiguous_context = {
        "target_program": "Computer Engineering",
        "catalog_degree_ambiguous": True,
    }

    systems_page = {
        "programme_ids": [
            "computer-engineering--master",
        ],
        "program_names": [
            "Computer Engineering",
        ],
        "degrees": [
            "Bachelor",
            "Master",
        ],
        "url": (
            "https://ce-master.htw-berlin.de/"
            "systems-engineering"
        ),
        "final_url": (
            "https://ce-master.htw-berlin.de/"
            "systems-engineering"
        ),
        "title": "Systems Engineering",
        "text": (
            "Systems Engineering "
            'Eine Bewerbung f\u00fcr den auslaufenden Masterstudiengang '
            '"Systems Engineering" ist nicht mehr m\u00f6glich. '
            "Abschluss Master of Engineering "
            "Unterrichtssprache Deutsch"
        ),
    }

    assert (
        evidence._programme_matches_page(
            ambiguous_context,
            systems_page,
        )
        is False
    )
