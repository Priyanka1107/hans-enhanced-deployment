from app.email.programme_guard import extract_unmatched_programme_name


def test_unknown_programme_without_in_is_detected():
    text = (
        "I am interested in the Master's programme "
        "Artificial Intelligence for Space Robotics at HTW Berlin."
    )

    assert (
        extract_unmatched_programme_name(text)
        == "Artificial Intelligence for Space Robotics"
    )


def test_existing_in_wording_still_works():
    text = (
        "I am interested in the Master's programme in "
        "Artificial Intelligence for Space Robotics."
    )

    assert (
        extract_unmatched_programme_name(text)
        == "Artificial Intelligence for Space Robotics"
    )


def test_generic_programme_overview_is_not_named_programme():
    text = (
        "Please list the Master's programmes offered at HTW Berlin."
    )

    assert extract_unmatched_programme_name(text) == ""


def test_descriptive_english_taught_bachelor_is_not_programme_title():
    text = (
        "I want to apply for the English-taught Bachelor?s in Business "
        "but am unsure whether I should apply as an EU applicant "
        "or international."
    )

    assert extract_unmatched_programme_name(text) == ""
