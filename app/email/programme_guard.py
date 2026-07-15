from __future__ import annotations

import re


def extract_unmatched_programme_name(email_text: str) -> str:
    raw = re.sub(r"\s+", " ", str(email_text or "")).strip()

    if not raw:
        return ""

    candidate = (
        r"([A-Za-zÄÖÜäöüß0-9&+\-/]+"
        r"(?:\s+[A-Za-zÄÖÜäöüß0-9&+\-/]+){1,11}?)"
    )
    end = r"(?=\s*(?:[?.!]|$))"

    patterns = [
        (
            r"\b(?:master(?:'s|’s)?(?:\s+(?:programme|program|degree))?|master)"
            r"\s+(?:in|of)\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:bachelor(?:'s|’s)?(?:\s+(?:programme|program|degree))?|bachelor)"
            r"\s+(?:in|of)\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:masterstudiengang|bachelorstudiengang)\s+(?:in\s+)?"
            + candidate
            + end
        ),
        (
            r"\b(?:what|which)\s+(?:is|are)\s+the\s+"
            r"(?:application\s+)?(?:deadline|application\s+period|requirements?)"
            r"\s+(?:for|of)\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:which|what)\s+(?:application\s+)?documents?"
            r"\s+do\s+(?:i|we)\s+need\s+for\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:i\s+(?:want|would\s+like|plan)\s+to\s+apply|"
            r"can\s+i\s+apply|how\s+do\s+i\s+apply)"
            r"\s+for\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:does|do)\s+HTW(?:\s+Berlin)?\s+offer\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:wie\s+lautet|was\s+ist)\s+die\s+"
            r"(?:bewerbungsfrist|bewerbungsphase|zulassungsvoraussetzung)"
            r"\s+für\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:welche|was\s+für)\s+unterlagen"
            r"(?:\s+benötige\s+ich|\s+brauche\s+ich)?"
            r"\s+für\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:ich\s+möchte\s+mich\s+bewerben|"
            r"kann\s+ich\s+mich\s+bewerben|"
            r"wie\s+bewerbe\s+ich\s+mich)"
            r"\s+für\s+"
            + candidate
            + end
        ),
        (
            r"\b(?:bietet)\s+die\s+HTW(?:\s+Berlin)?\s+"
            + candidate
            + end
        ),
    ]

    generic_exact = {
        "master programme",
        "master program",
        "master programmes",
        "master programs",
        "master s programme",
        "master s program",
        "master s programmes",
        "master s programs",
        "bachelor programme",
        "bachelor program",
        "bachelor programmes",
        "bachelor programs",
        "bachelor s programme",
        "bachelor s program",
        "bachelor s programmes",
        "bachelor s programs",
        "degree programme",
        "degree program",
        "degree programmes",
        "degree programs",
        "study programme",
        "study program",
        "study programmes",
        "study programs",
        "a programme",
        "a program",
        "the programme",
        "the program",
        "any programme",
        "any program",
        "another programme",
        "another program",
        "one programme",
        "one program",
        "more than one programme",
        "more than one program",
        "programmes",
        "programs",
        "programme",
        "program",
    }

    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)

        if not match:
            continue

        value = re.sub(
            r"\s+",
            " ",
            match.group(1),
        ).strip(" ,.-")

        value = re.sub(
            r"\s+(?:at|an der)\s+HTW(?: Berlin)?$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        value = re.sub(
            r"\s+(?:for|in)\s+(?:the\s+)?(?:winter|summer)\s+semester.*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        value = re.sub(
            r"\s+(?:für|im)\s+(?:das\s+)?(?:winter|sommer)semester.*$",
            "",
            value,
            flags=re.IGNORECASE,
        ).strip()

        normalised = re.sub(
            r"[^a-z0-9äöüß]+",
            " ",
            value.lower(),
        ).strip()

        if normalised in generic_exact:
            continue

        word_count = len(value.split())

        if word_count < 2 or word_count > 12:
            continue

        return value

    return ""


def build_unconfirmed_programme_draft(
    programme_name: str,
    reply_language: str,
) -> str:
    programme_name = str(
        programme_name or "the programme mentioned"
    ).strip()

    if str(reply_language or "").lower().startswith("de"):
        return (
            "Sehr geehrte/r Bewerber/in,\n\n"
            "vielen Dank für Ihre Anfrage.\n\n"
            "Im aktuellen Studiengangskatalog der HTW Berlin ist kein "
            f"Studiengang mit der genauen Bezeichnung „{programme_name}“ "
            "aufgeführt. Bitte prüfen Sie die Bezeichnung oder senden Sie "
            "uns den offiziellen Link zum gemeinten Studiengang.\n\n"
            "Da Bewerbungsfristen und erforderliche Unterlagen vom jeweiligen "
            "Studiengang abhängen, können wir erst nach der eindeutigen "
            "Zuordnung verlässliche studiengangsspezifische Angaben machen.\n\n"
            "Mit freundlichen Grüßen\n"
            "HTW Berlin Student Services\n\n"
            "Referenzlink zur Prüfung durch Mitarbeitende:\n"
            "- Studiengänge der HTW Berlin: "
            "https://www.htw-berlin.de/studium/studiengaenge/"
        )

    return (
        "Dear applicant,\n\n"
        "Thank you for your enquiry.\n\n"
        "HTW Berlin does not currently list a degree programme with the "
        f'exact name "{programme_name}". Please check the programme name '
        "or send us the official programme link.\n\n"
        "Application deadlines and required documents differ by programme, "
        "so we cannot provide reliable programme-specific information until "
        "the programme has been identified.\n\n"
        "Kind regards,\n"
        "HTW Berlin Student Services\n\n"
        "Reference link for staff verification:\n"
        "- HTW Berlin degree programmes: "
        "https://www.htw-berlin.de/en/studies/degree-programmes/"
    )
