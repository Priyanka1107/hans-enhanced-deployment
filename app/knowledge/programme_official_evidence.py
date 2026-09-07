"""
Programme-specific official evidence helper.

Loads:
    data/programme_official_pages.json

Purpose:
    Add official programme-page snippets to retrieval results when the student
    asks programme-specific questions such as fees, work experience, language
    proof, documents, or study format.

This avoids answering specific programme questions from overly general HTW pages.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = PROJECT_ROOT / "data" / "programme_official_pages.json"


TOPIC_KEYWORDS = {
    "programme_overview": [
        "degree programmes",
        "study programmes",
        "master",
        "masters",
        "master's",
        "master programme",
        "master programmes",
        "master's degree programmes",
        "advanced master's programmes",
        "programme list",
        "program list",
        "programme overview",
        "study programme overview",
        "studienangebot",
        "studiengänge",
        "masterstudiengänge",
    ],
    "tuition_fees": [
        "tuition",
        "tuition fees",
        "programme fee",
        "program fee",
        "fees",
        "financing",
        "instalment",
        "installment",
        "15,750",
        "15.750",
        "17,600",
        "17.600",
        "5,250",
        "5.250",
        "4,400",
        "4.400",
    ],
    "fees": [
        "tuition",
        "tuition fees",
        "semester fees",
        "programme fee",
        "fees",
        "financing",
        "instalment",
        "installment",
    ],
    "application_fee": [
        "application fee",
        "processing fee",
        "uni-assist",
        "handling fees",
        "processing costs",
    ],
    "work_experience": [
        "work experience",
        "professional experience",
        "relevant professional experience",
        "one year",
        "at least one year",
    ],
    "english_language_requirements": [
        "english",
        "english proficiency",
        "proof of english",
        "ielts",
        "toefl",
        "toeic",
        "cambridge",
        "language proof",
    ],
    "german_language_requirements": [
        "german",
        "proof of german",
        "german language",
        "language proof",
    ],
    "language_of_instruction": [
        "teaching language",
        "language of instruction",
        "taught entirely in english",
        "taught in english",
        "english-taught",
        "english taught",
        "unterrichtssprache",
    ],
    "study_format": [
        "study format",
        "mode of study",
        "on campus",
        "on-campus",
        "online learning",
        "online participation",
        "online programme",
        "online program",
        "distance learning",
        "pr?senzstudium",
        "fernstudium",
        "streamed",
        "video conference",
        "video conferences",
        "simultaneously streamed",
        "attendance",
    ],
    "required_documents": [
        "documents",
        "application documents",
        "transcript",
        "certificate",
        "upload",
        "proof",
    ],
    "admission_requirements": [
        "admission requirements",
        "required qualifications",
        "bachelor",
        "ects",
        "credit points",
        "requirements",
    ],
    "application_route": [
        "apply",
        "application",
        "application form",
        "application portal",
        "uni-assist",
        "hochschulstart",
    ],
    "application_deadline": [
        "deadline",
        "application period",
        "apply by",
        "application deadline",
    ],
}


# Strong phrases distinguish actual topic evidence from
# merely related wording elsewhere on a programme page.
TOPIC_STRONG_KEYWORDS: Dict[str, List[str]] = {
    "language_of_instruction": [
        "teaching language",
        "language of instruction",
        "taught entirely in english",
        "taught in english",
        "english-taught",
        "english taught",
        "unterrichtssprache",
    ],
    "study_format": [
        "on-campus",
        "on campus",
        "online learning",
        "online participation",
        "distance learning",
        "pr?senzstudium",
        "fernstudium",
        "simultaneously streamed",
        "interactive video conference",
        "interactive video conferences",
    ],
    "application_deadline": [
        "application deadline",
        "application period",
        "applications open",
        "applications welcome",
        "apply by",
    ],
    "required_documents": [
        "required documents",
        "application documents",
        "submit the following documents",
        "degree certificate",
        "grade transcript",
    ],
    "english_language_requirements": [
        "proof of english",
        "english proficiency",
        "toefl",
        "ielts",
        "pte academic",
        "toeic",
        "cambridge",
    ],
}


# Pages whose purpose is clearly unrelated to a topic must
# not become evidence merely because they contain one keyword.
TOPIC_EXCLUDED_PATH_FRAGMENTS: Dict[
    str,
    Tuple[str, ...],
] = {
    "application_deadline": (
        "finances",
        "fees-financing",
        "scholarship",
        "refund",
        "master-thesis",
        "masters-thesis",
        "thesis",
        "abschlussarbeit",
    ),
    "required_documents": (
        "finances",
        "fees-financing",
        "scholarship",
        "master-thesis",
        "masters-thesis",
        "thesis",
        "abschlussarbeit",
    ),
    "english_language_requirements": (
        "finances",
        "fees-financing",
        "scholarship",
    ),
    "language_of_instruction": (
        "finances",
        "fees-financing",
        "scholarship",
    ),
    "study_format": (
        "finances",
        "fees-financing",
        "scholarship",
    ),
}


# These topics are too sensitive for a weak keyword match.
# At least one strong phrase must be present.
TOPICS_REQUIRING_STRONG_EVIDENCE = {
    "language_of_instruction",
    "study_format",
    "application_deadline",
    "required_documents",
}


def _load_cache() -> List[Dict[str, Any]]:
    if not CACHE_PATH.exists():
        return []

    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
    except Exception:
        return []

    return []


def _normalise(value: str) -> str:
    value = str(value or "").lower()
    value = re.sub(r"[^a-z0-9äöüß]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _programme_matches_page(context: Dict[str, Any], page: Dict[str, Any]) -> bool:
    target_program = _normalise(context.get("target_program") or context.get("matched_programme") or "")
    target_url = str(
        context.get("target_program_url")
        or context.get("matched_programme_url")
        or context.get("programme_url")
        or ""
    )

    page_program = _normalise(page.get("program_name") or "")
    page_url = str(page.get("url") or page.get("final_url") or "")

    if target_program and page_program and target_program == page_program:
        return True

    if target_program and page_program and (target_program in page_program or page_program in target_program):
        return True

    if target_url and page_url and _host(target_url) == _host(page_url):
        return True

    aliases = page.get("aliases", []) or []
    for alias in aliases:
        alias_norm = _normalise(str(alias))
        if alias_norm and target_program and alias_norm in target_program:
            return True

    return False


def _topic_terms(topic_id: str) -> List[str]:
    terms = list(TOPIC_KEYWORDS.get(topic_id, []))

    # Some scripts use general "fees" instead of tuition_fees.
    if topic_id in {"fees", "application_fee", "tuition_fees", "semester_contribution"}:
        terms.extend(TOPIC_KEYWORDS["tuition_fees"])

    return list(dict.fromkeys(terms))


def _strong_terms(topic_id: str) -> List[str]:
    return list(
        dict.fromkeys(
            TOPIC_STRONG_KEYWORDS.get(
                topic_id,
                [],
            )
        )
    )


def _find_best_snippet(
    text: str,
    terms: List[str],
    *,
    topic_id: str = "",
    max_chars: int = 1800,
) -> str:
    """
    Select the strongest topic-specific evidence window.

    Do not return an arbitrary beginning-of-page fragment when
    the page contains no actual evidence for the requested topic.
    """
    clean_text = re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()

    if not clean_text:
        return ""

    lower = clean_text.lower()

    strong_terms = _strong_terms(topic_id)

    ordered_terms = list(
        dict.fromkeys(
            strong_terms + list(terms)
        )
    )

    candidate_positions: List[int] = []

    for term in ordered_terms:
        needle = term.lower()
        start = 0

        while needle:
            position = lower.find(
                needle,
                start,
            )

            if position < 0:
                break

            candidate_positions.append(position)
            start = position + max(
                1,
                len(needle),
            )

    if not candidate_positions:
        return ""

    best_window = ""
    best_score = -1

    for position in sorted(
        set(candidate_positions)
    ):
        window_start = max(
            0,
            position - 400,
        )

        window_end = min(
            len(clean_text),
            window_start + max_chars,
        )

        window = clean_text[
            window_start:window_end
        ].strip()

        window_lower = window.lower()

        score = 0

        for term in strong_terms:
            if term.lower() in window_lower:
                score += 8

        for term in terms:
            if term.lower() in window_lower:
                score += 2

        if topic_id == "application_deadline":
            if re.search(
                r"\b\d{1,2}\s+"
                r"(january|february|march|april|may|june|"
                r"july|august|september|october|november|"
                r"december)\b",
                window_lower,
            ):
                score += 12

            if re.search(
                r"\b\d{1,2}[./-]\d{1,2}"
                r"(?:[./-]\d{2,4})?\b",
                window_lower,
            ):
                score += 10

        elif topic_id == "study_format":
            if any(
                phrase in window_lower
                for phrase in (
                    "online learning",
                    "online participation",
                    "simultaneously streamed",
                    "interactive video conference",
                    "interactive video conferences",
                )
            ):
                score += 20

        elif topic_id == "language_of_instruction":
            if any(
                phrase in window_lower
                for phrase in (
                    "teaching language",
                    "language of instruction",
                    "english-taught",
                    "english taught",
                    "taught in english",
                )
            ):
                score += 20

        elif topic_id == "required_documents":
            if (
                "submit the following documents"
                in window_lower
            ):
                score += 20

        if score > best_score:
            best_score = score
            best_window = window

    if best_score <= 0:
        return ""

    return best_window


def _page_score(
    page: Dict[str, Any],
    topic_id: str,
) -> int:
    url = str(
        page.get("final_url")
        or page.get("url")
        or ""
    ).lower()

    title = str(
        page.get("title")
        or ""
    ).lower()

    text = str(
        page.get("text")
        or ""
    ).lower()

    terms = _topic_terms(topic_id)
    strong_terms = _strong_terms(topic_id)

    excluded = (
        TOPIC_EXCLUDED_PATH_FRAGMENTS.get(
            topic_id,
            (),
        )
    )

    if any(
        fragment in url
        for fragment in excluded
    ):
        return 0

    strong_present = any(
        term.lower() in text
        for term in strong_terms
    )

    if (
        topic_id
        in TOPICS_REQUIRING_STRONG_EVIDENCE
        and not strong_present
    ):
        return 0

    score = 0

    for term in terms:
        term_lower = term.lower()

        if term_lower in title:
            score += 5

        if term_lower in url:
            score += 5

        if term_lower in text:
            score += 2

    for term in strong_terms:
        term_lower = term.lower()

        if term_lower in title:
            score += 10

        if term_lower in url:
            score += 10

        if term_lower in text:
            score += 8

    if topic_id == "work_experience":
        if (
            "applying" in url
            or "faq" in url
        ):
            score += 8

        if "professional experience" in text:
            score += 15

    elif topic_id in {
        "admission_requirements",
        "application_route",
    }:
        if "applying" in url:
            score += 10

    elif topic_id == "english_language_requirements":
        if re.search(
            r"\b(toefl|ielts|pte|toeic|cambridge)\b",
            text,
        ):
            score += 25

        if re.search(
            r"\b(b2|c1|c2)\b",
            text,
        ):
            score += 15

    elif topic_id == "language_of_instruction":
        if strong_present:
            score += 30

    elif topic_id == "study_format":
        if any(
            phrase in text
            for phrase in (
                "online learning",
                "online participation",
                "simultaneously streamed",
                "interactive video conference",
                "interactive video conferences",
            )
        ):
            score += 35

    elif topic_id == "application_deadline":
        if re.search(
            r"\b\d{1,2}\s+"
            r"(january|february|march|april|may|june|"
            r"july|august|september|october|november|"
            r"december)\b",
            text,
        ):
            score += 20

        if re.search(
            r"\b\d{1,2}[./-]\d{1,2}"
            r"(?:[./-]\d{2,4})?\b",
            text,
        ):
            score += 15

    elif topic_id == "required_documents":
        if "applying" in url:
            score += 10

        if (
            "submit the following documents"
            in text
        ):
            score += 25

    elif topic_id in {
        "tuition_fees",
        "fees",
        "semester_contribution",
    }:
        if any(
            fragment in url
            for fragment in (
                "fees-financing",
                "finances",
                "organise-your-finances",
            )
        ):
            score += 15

    return score


def get_official_programme_docs(
    context: Dict[str, Any],
    topic_id: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """
    Return programme-specific official page snippets as retrieval documents.
    """
    if not context.get("target_program") and not context.get("matched_programme"):
        return []

    cache = _load_cache()
    if not cache:
        return []

    matching_pages = [
        page
        for page in cache
        if _programme_matches_page(context, page)
    ]

    if not matching_pages:
        return []

    scored = [
        (page, _page_score(page, topic_id))
        for page in matching_pages
    ]

    scored.sort(key=lambda item: item[1], reverse=True)

    selected = [
        page
        for page, score in scored
        if score > 0
    ][:limit]

    docs: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    terms = _topic_terms(topic_id)

    for index, page in enumerate(selected, start=1):
        page_text = str(page.get("text") or "")
        snippet = _find_best_snippet(
            page_text,
            terms,
            topic_id=topic_id,
        )

        if not snippet:
            continue

        url = str(
            page.get("final_url")
            or page.get("url")
            or ""
        ).strip()

        url_key = url.lower().rstrip("/")

        if not url_key or url_key in seen_urls:
            continue

        seen_urls.add(url_key)

        docs.append(
            {
                "id": f"official_programme_page::{page.get('program_name')}::{url}::{topic_id}",
                "title": page.get("title") or page.get("program_name") or "Official programme page",
                "content": snippet,
                "chunk_text": snippet,
                "source_url": url,
                "url": url,
                "object_type": "official_programme_page_cache",
                "object_id": page.get("program_name") or "",
                "score": 1.0,
                "metadata": {
                    "program_name": page.get("program_name"),
                    "topic_id": topic_id,
                    "retrieved_at": page.get("retrieved_at"),
                    "source": "official_programme_page_cache",
                },
            }
        )

    return docs