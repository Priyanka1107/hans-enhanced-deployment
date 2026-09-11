"""
Programme-specific official evidence helper.

The programme page cache is deliberately kept separate from the generic vector
store.  Programme-specific facts (deadline, language proof, fees, format, etc.)
should preferentially come from these official pages.

Important design rules:
- programme/degree applicability is checked before a page is used;
- duplicate cache records are collapsed;
- snippets are selected around the *strongest topic evidence*, not simply the
  first occurrence of a generic word such as "English";
- if a page has no evidence for the requested topic, it is not returned as a
  fallback source;
- application fees, tuition fees and semester contribution are separate topics.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse, urlunparse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_PATH = PROJECT_ROOT / "data" / "programme_official_pages.json"


# General topic terms.  These are deliberately more complete than the old map so
# every programme-specific topic emitted by app.email.multitopic has useful
# anchors instead of silently falling back to the first 1,200 characters.
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "programme_overview": [
        "programme overview",
        "program overview",
        "degree",
        "duration",
        "teaching language",
        "location",
        "total credits",
        "full-time",
        "part-time",
    ],
    "programme_start": [
        "start every semester",
        "starts every semester",
        "start semester",
        "study start",
        "summer semester",
        "winter semester",
        "summer intake",
        "winter intake",
        "next intake",
        "next intakes",
        "intake",
        "duration and start",
    ],
    "programme_duration": [
        "regelstudienzeit",
        "standard duration",
        "regular study period",
        "duration",
        "semesters",
        "semester",
        "total credits",
    ],
    "application_deadline": [
        "application deadline",
        "application period",
        "applications open",
        "applications welcome",
        "apply by",
        "deadline",
        # German HTW programme pages
        "bewerbungsfrist",
        "bewerbungszeitraum",
        "bewerbungsschluss",
        "letzte tag f?r die bewerbung",
        "letzter tag f?r die bewerbung",
    ],
    "admission_requirements": [
        "admission requirements",
        "do i qualify",
        "requirements",
        "bachelor degree",
        "ects",
        "credit points",
        "professional experience",
    ],
    "required_documents": [
        "required documents",
        "documents",
        "degree certificate",
        "grade transcript",
        "transcript",
        "curriculum vitae",
        "passport",
        "proof",
    ],
    "work_experience": [
        "professional experience",
        "work experience",
        "one year",
        "at least one year",
        "employer",
    ],
    "english_language_requirements": [
        "proof of english proficiency",
        "proof of english language proficiency",
        "english language skills",
        "english proficiency",
        "toefl",
        "ielts",
        "pte academic",
        "toeic",
        "cambridge",
        "cefr",
        "language proof",
    ],
    "german_language_requirements": [
        "proof of german",
        "german language proficiency",
        "german proficiency",
        "telc",
        "testdaf",
        "dsh",
        "goethe",
        "cefr",
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
        "full-time",
        "part-time",
        "on-campus",
        "on campus",
        "presence study",
        "präsenzstudium",
        "distance learning",
        "fernstudium",
        "online learning",
        "online participation",
        "streamed",
        "video conference",
        "video conferences",
        "simultaneously streamed",
        "campus",
    ],
    "application_route": [
        "application portal",
        "online application",
        "uni-assist",
        "hochschulstart",
        "dosv",
        "how to apply",
        "application form",
        # German HTW programme pages
        "online-bewerbung",
        "online bewerben",
        "bewerbungsportal",
        "online-bewerbungsportal",
        "bewerbungsprozess",
    ],
    "application_process": [
        "how to apply",
        "application process",
        "online application",
        "application form",
        "application portal",
    ],
    "application_before_graduation": [
        "final semester",
        "before graduation",
        "before receiving",
        "final transcript",
        "final degree certificate",
        "degree certificate",
        "currently in the final semester",
        "provisional transcript",
        "submit later",
        "after admission",
        "after enrolment",
    ],
    "final_certificate_submission": [
        "final degree certificate",
        "final certificate",
        "degree certificate",
        "final transcript",
        "submit later",
        "after admission",
        "after enrolment",
        "enrolment deadline",
        "proof of completed studies",
    ],
    "application_fee": [
        "application fee",
        "application fees",
        "processing fee",
        "processing fees",
        "processing costs",
        "handling fee",
        "handling fees",
        "uni-assist fee",
        "uni-assist fees",
    ],
    "tuition_fees": [
        "tuition fee",
        "tuition fees",
        "tuition",
        "programme fee",
        "program fee",
        "study fees",
    ],
    "fees": [
        "tuition fee",
        "semester fee",
        "programme fee",
        "fees",
    ],
    "semester_contribution": [
        "semester contribution",
        "semester fee",
        "semester fees",
        "semesterbeitrag",
        "semesterticket",
        "deutschlandticket",
    ],
    "motivation_letter": [
        "letter of motivation",
        "motivation letter",
        "video of motivation",
        "motivation video",
    ],
    "aps_certificate": [
        "aps certificate",
        "academic test centre",
        "academic evaluation centre",
        "china",
        "vietnam",
        "india",
    ],
    "certified_translations": [
        "certified translation",
        "translation",
        "translated",
        "english or german",
    ],
    "hard_copy_documents": [
        "hard copy",
        "hard copies",
        "certified official copies",
        "mail us",
        "send by post",
    ],
    "document_uploads": [
        "upload",
        "online application form",
        "submit the following documents",
        "application portal",
    ],
    "conditional_enrolment": [
        "conditional enrolment",
        "conditional admission",
        "provisional admission",
        "after enrolment",
        "after admission",
    ],
    "credit_recognition": [
        "credit recognition",
        "recognition of credits",
        "recognition of academic achievements",
        "transfer credits",
    ],
    "grade_conversion": [
        "grade conversion",
        "grading system",
        "grade transcript",
        "average grade",
    ],
    "qualification_recognition": [
        "qualification recognition",
        "higher education entrance qualification",
        "foreign qualification",
        "anabin",
        "daad admission database",
    ],
}


# Strong anchors receive substantially more weight.  For English requirements,
# for example, TOEFL/IELTS/PTE/CEFR are more useful than the first generic word
# "English" on the page.  The strongest window is placed first so it survives
# downstream prompt-length limits.
TOPIC_STRONG_KEYWORDS: Dict[str, List[str]] = {
    "english_language_requirements": [
        "toefl",
        "ielts",
        "pte academic",
        "toeic",
        "cambridge",
        "cefr",
        "english language skills",
        "proof of english proficiency",
    ],
    "german_language_requirements": [
        "testdaf",
        "dsh",
        "telc",
        "goethe",
        "cefr",
        "proof of german",
    ],
    "application_before_graduation": [
        "currently in the final semester",
        "final semester",
        "before graduation",
        "final transcript",
        "final degree certificate",
        "submit later",
    ],
    "final_certificate_submission": [
        "final degree certificate",
        "certified official copies",
        "submit later",
        "after admission",
        "after enrolment",
    ],
    "application_fee": [
        "application fee",
        "processing fee",
        "processing costs",
        "handling fee",
        "uni-assist fee",
    ],
    "tuition_fees": [
        "tuition fee",
        "tuition fees",
        "programme fee",
        "program fee",
    ],
    "semester_contribution": [
        "semester contribution",
        "semester fee",
        "semesterbeitrag",
    ],
    "programme_start": [
        "start every semester",
        "starts every semester",
        "summer semester",
        "winter semester",
        "summer intake",
        "winter intake",
        "next intake",
        "next intakes",
        "start of studies",
        "duration and start",
    ],
    "programme_duration": [
        "regelstudienzeit",
        "standard duration",
        "regular study period",
        "duration",
    ],
    "application_deadline": [
        "application period",
        "application deadline",
        "applications open",
        # German direct deadline evidence
        "bewerbungsfrist",
        "bewerbungszeitraum",
        "bewerbungsschluss",
    ],
    "required_documents": [
        "required documents",
        "submit the following documents",
        "attached to the online application",
        "degree certificate",
        "grade transcript",
        "submission of proof",
        "proof of completion",
        "proof of english proficiency",
        "proof of english language proficiency",
    ],
    "study_format": [
        "präsenzstudium",
        "distance learning",
        "fernstudium",
        "full-time",
        "part-time",
        "on-campus",
        "online learning",
        "online participation",
        "simultaneously streamed",
        "interactive video conferences",
    ],
    "language_of_instruction": [
        "teaching language",
        "language of instruction",
        "taught in english",
        "english-taught",
    ],
}




TOPIC_EXCLUDED_PATH_FRAGMENTS: Dict[str, Tuple[str, ...]] = {
    "programme_start": ("master-thesis", "masters-thesis", "thesis", "abschlussarbeit", "finances", "fees-financing", "scholarship", "programme-regulations", "regulations-modules", "study-examination-regulations", "ordnungen-module"),
    "programme_duration": ("master-thesis", "masters-thesis", "thesis", "abschlussarbeit", "finances", "fees-financing", "scholarship"),
    "application_deadline": ("finances", "fees-financing", "scholarship", "refund", "master-thesis", "masters-thesis", "thesis", "abschlussarbeit"),
    "required_documents": ("finances", "fees-financing", "scholarship", "master-thesis", "masters-thesis", "thesis", "abschlussarbeit", "thesis-topics"),
    "english_language_requirements": ("finances", "fees-financing", "scholarship"),
    "application_before_graduation": ("finances", "fees-financing", "scholarship"),
    "final_certificate_submission": ("finances", "fees-financing", "scholarship"),
    "study_format": ("finances", "fees-financing", "scholarship"),
}

# For these high-risk topics a path match or a weak generic word is not enough.
# The page must contain at least one strong evidence phrase.
TOPICS_REQUIRING_STRONG_EVIDENCE = {
    "programme_start",
    "programme_duration",
    "required_documents",
    "study_format",
    "application_before_graduation",
    "final_certificate_submission",
    "application_fee",
}

TOPIC_PATH_HINTS: Dict[str, Tuple[str, ...]] = {
    "programme_start": ("overview", "study", "studying", "master", "bachelor", "apply", "applying", "application"),
    "programme_duration": ("overview", "study", "studying", "master", "bachelor"),
    "application_deadline": (
        "apply",
        "applying",
        "application",
        "admission",
        "bewerbung",
    ),
    "admission_requirements": ("apply", "applying", "admission", "requirements"),
    "required_documents": ("apply", "applying", "application", "documents"),
    "work_experience": ("apply", "applying", "application", "admission", "faq"),
    "english_language_requirements": ("apply", "applying", "application", "admission", "language", "faq"),
    "german_language_requirements": ("apply", "applying", "application", "admission", "language", "faq"),
    "application_before_graduation": ("apply", "applying", "application", "admission", "faq"),
    "final_certificate_submission": ("apply", "applying", "application", "admission", "faq"),
    "application_route": (
        "apply",
        "applying",
        "application",
        "bewerbung",
    ),
    "application_process": ("apply", "applying", "application"),
    "application_fee": ("apply", "applying", "application", "fee", "faq"),
    "tuition_fees": ("fee", "fees", "financ", "cost"),
    "semester_contribution": ("fee", "fees", "financ", "cost"),
    "study_format": ("study", "studying", "overview", "master", "bachelor"),
    "language_of_instruction": ("study", "studying", "overview", "master", "bachelor"),
}


def _load_cache() -> List[Dict[str, Any]]:
    if not CACHE_PATH.exists():
        return []

    try:
        with CACHE_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("pages", "programme_pages", "programmes"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _normalise(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"&", " and ", text)
    text = re.sub(r"[^a-z0-9äöüß]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalise_degree(value: Any) -> str:
    text = _normalise(value)
    if not text or text == "unknown":
        return ""
    if "bachelor" in text:
        return "Bachelor"
    if "master" in text or text == "mba":
        return "Master"
    return ""


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _canonical_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
        path = re.sub(r"/{2,}", "/", parsed.path or "/")
        if path != "/":
            path = path.rstrip("/")
        cleaned = parsed._replace(
            scheme=(parsed.scheme or "https").lower(),
            netloc=parsed.netloc.lower(),
            path=path,
            params="",
            query="",
            fragment="",
        )
        return urlunparse(cleaned)
    except Exception:
        return raw.rstrip("/")


def _page_programme_names(page: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for key in ("program_name", "programme_name"):
        value = str(page.get(key) or "").strip()
        if value:
            values.append(value)
    for key in ("program_names", "programme_names"):
        raw = page.get(key)
        if isinstance(raw, list):
            values.extend(str(value).strip() for value in raw if str(value).strip())
    return list(dict.fromkeys(values))


def _page_programme_ids(page: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    value = str(page.get("programme_id") or page.get("program_id") or "").strip()
    if value:
        values.append(value)
    raw = page.get("programme_ids") or page.get("program_ids")
    if isinstance(raw, list):
        values.extend(str(item).strip() for item in raw if str(item).strip())
    return list(dict.fromkeys(values))


def _page_degrees(
    page: Dict[str, Any],
) -> set[str]:
    """
    Return the degree variant(s) represented by an official page.

    An explicit /master/ or /bachelor/ URL path is authoritative.
    This protects against legacy cache records whose association
    metadata accidentally contains both degree variants.

    Combined/non-degree-specific pages may still represent both.
    """
    page_url = str(
        page.get("final_url")
        or page.get("url")
        or ""
    )

    try:
        path = urlparse(
            page_url
        ).path.lower()
    except Exception:
        path = ""

    if re.search(
        r"(?:^|/)master(?:/|$)",
        path,
    ):
        return {"Master"}

    if re.search(
        r"(?:^|/)bachelor(?:/|$)",
        path,
    ):
        return {"Bachelor"}

    degrees: set[str] = set()

    for key in (
        "degree",
        "degree_level",
    ):
        degree = _normalise_degree(
            page.get(key)
        )

        if degree:
            degrees.add(degree)

    raw_degrees = (
        page.get("degrees")
        or page.get("degree_levels")
    )

    if isinstance(
        raw_degrees,
        list,
    ):
        for raw in raw_degrees:
            degree = _normalise_degree(
                raw
            )

            if degree:
                degrees.add(degree)

    # For genuinely shared pages, title metadata remains
    # a useful backstop.
    title = _normalise(
        page.get("title")
    )

    if "bachelor" in title:
        degrees.add("Bachelor")

    if "master" in title:
        degrees.add("Master")

    return degrees


def _deduplicate_pages(pages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Collapse duplicate cache entries while retaining the richest record."""
    by_url: Dict[str, Dict[str, Any]] = {}

    for page in pages:
        url = _canonical_url(str(page.get("final_url") or page.get("url") or ""))
        if not url:
            continue

        existing = by_url.get(url)
        if existing is None:
            by_url[url] = dict(page)
            continue

        existing_text = str(existing.get("text") or "")
        new_text = str(page.get("text") or "")
        if len(new_text) > len(existing_text):
            richer = dict(page)
            poorer = existing
        else:
            richer = existing
            poorer = page

        # Merge association metadata so a shared programme homepage can safely
        # represent both Bachelor and Master variants.
        programme_names = _page_programme_names(richer) + _page_programme_names(poorer)
        programme_ids = _page_programme_ids(richer) + _page_programme_ids(poorer)
        degrees = sorted(_page_degrees(richer) | _page_degrees(poorer))

        richer["program_names"] = list(dict.fromkeys(programme_names))
        richer["programme_ids"] = list(dict.fromkeys(programme_ids))
        richer["degrees"] = degrees
        richer["final_url"] = str(richer.get("final_url") or richer.get("url") or url)
        by_url[url] = richer

    return list(by_url.values())


def _programme_matches_page(context: Dict[str, Any], page: Dict[str, Any]) -> bool:
    target_program = _normalise(
        context.get("target_program")
        or context.get("matched_programme")
        or context.get("target_programme")
        or ""
    )
    target_programme_id = str(context.get("programme_id") or "").strip()
    target_degree = _normalise_degree(context.get("target_degree") or context.get("catalog_degree"))
    target_url = str(
        context.get("target_program_url")
        or context.get("matched_programme_url")
        or context.get("programme_url")
        or ""
    )

    page_programme_ids = _page_programme_ids(page)
    page_programmes = [_normalise(value) for value in _page_programme_names(page)]
    page_url = str(page.get("final_url") or page.get("url") or "")
    page_degrees = _page_degrees(page)

    degree_compatible = not target_degree or not page_degrees or target_degree in page_degrees
    if not degree_compatible:
        return False

    if target_programme_id and target_programme_id in page_programme_ids:
        return True

    if target_program and page_programmes:
        if any(target_program == name for name in page_programmes):
            return True
        if any(target_program in name or name in target_program for name in page_programmes if name):
            return True

    if target_url and page_url and _host(target_url) == _host(page_url):
        return True

    aliases = page.get("aliases", []) or []
    for alias in aliases:
        alias_norm = _normalise(alias)
        if alias_norm and target_program and (
            alias_norm == target_program
            or alias_norm in target_program
            or target_program in alias_norm
        ):
            return True

    return False


def _topic_terms(topic_id: str) -> List[str]:
    return list(dict.fromkeys(TOPIC_KEYWORDS.get(topic_id, [])))


def _strong_terms(topic_id: str) -> List[str]:
    return list(dict.fromkeys(TOPIC_STRONG_KEYWORDS.get(topic_id, [])))


def _find_all_positions(lower_text: str, term: str) -> List[int]:
    positions: List[int] = []
    start = 0
    needle = term.lower()
    while needle and start < len(lower_text):
        pos = lower_text.find(needle, start)
        if pos < 0:
            break
        positions.append(pos)
        start = pos + max(1, len(needle))
    return positions


def _window_score(window: str, topic_id: str) -> float:
    lower = window.lower()
    score = 0.0

    strong = _strong_terms(topic_id)
    general = _topic_terms(topic_id)

    for term in strong:
        count = lower.count(term.lower())
        if count:
            score += 8.0 * min(count, 3)

    for term in general:
        count = lower.count(term.lower())
        if count:
            score += 2.0 * min(count, 3)

    # Reward evidence-rich patterns for topics where exact values matter.
    if topic_id == "english_language_requirements":
        if re.search(r"\b(b2|c1|c2)\b", lower):
            score += 8
        if re.search(r"\b(toefl|ielts|pte|toeic)\b.{0,80}\b\d", lower):
            score += 12
    elif topic_id == "application_deadline":
        if re.search(r"\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b", lower):
            score += 10
        if re.search(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b", lower):
            score += 8
    elif topic_id == "required_documents":
        # Prefer the actual programme application list over an earlier phrase
        # such as "prepare the required documents (see below)".  This keeps
        # passport/CV/language/work-experience items inside the downstream
        # prompt window instead of spending that window on page introduction.
        if "submit the following documents" in lower:
            score += 24
        if "attached to the online application" in lower:
            score += 12
        for phrase in (
            "degree certificate",
            "grade transcript",
            "professional experience",
            "proof of english",
            "passport",
            "curriculum vitae",
        ):
            if phrase in lower:
                score += 4
    elif topic_id in {"application_fee", "tuition_fees", "semester_contribution"}:
        if re.search(r"(?:€|eur|euro|\$)\s*\d|\b\d[\d,.]*\s*(?:€|eur|euro)\b", lower):
            score += 8
    elif topic_id in {"application_before_graduation", "final_certificate_submission"}:
        if "final semester" in lower or "final degree certificate" in lower:
            score += 10
        if "after admission" in lower or "after enrolment" in lower or "submit later" in lower:
            score += 8

    return score


def _find_best_snippet(
    text: str,
    terms: Sequence[str],
    *,
    topic_id: str = "",
    max_chars: int = 2600,
) -> str:
    """
    Return the highest-information topic window.

    The old implementation chose the earliest matching word.  That caused the
    MPMD English snippet to stop at "Acceptable documents include:" even though
    TOEFL/IELTS/PTE thresholds appeared later on the same page.  This version
    scores windows around strong and general anchors and returns the strongest
    evidence first.
    """
    if not text:
        return ""

    clean_text = re.sub(r"\s+", " ", str(text)).strip()
    lower = clean_text.lower()
    if not lower:
        return ""

    strong = _strong_terms(topic_id)
    ordered_terms = list(dict.fromkeys([*strong, *terms]))

    candidate_positions: List[int] = []
    for term in ordered_terms:
        candidate_positions.extend(_find_all_positions(lower, term))

    if not candidate_positions:
        # Returning an unrelated first-page fragment is more dangerous than
        # returning no programme-specific evidence.  Generic DB retrieval can
        # still provide backup evidence.
        return ""

    # Build windows large enough to capture a heading plus the detailed rule.
    # For document-list questions, keep less text before the anchor so the full
    # application list is not pushed out of the LLM's per-document prompt window.
    candidates: List[Tuple[float, float, int, int, str]] = []
    left_context = 160 if topic_id == "required_documents" else 500

    for pos in sorted(set(candidate_positions)):
        start = max(0, pos - left_context)
        end = min(len(clean_text), start + max_chars)
        window = clean_text[start:end].strip()
        score = _window_score(window, topic_id)

        # Tie-break with a much smaller anchor-local window.  This matters on
        # long pages where a generic early occurrence (for example the word
        # TOEFL in an accepted-document list) and a later exact threshold block
        # both fall inside the same 2,600-character candidate window.  The
        # numeric/CEFR-rich block should be placed first so downstream prompt
        # truncation cannot hide the decisive values.
        local_start = max(0, pos - 220)
        local_end = min(len(clean_text), pos + 420)
        local_score = _window_score(
            clean_text[local_start:local_end],
            topic_id,
        )
        candidates.append((score, local_score, start, end, window))

    if topic_id in {
        "english_language_requirements",
        "german_language_requirements",
        "required_documents",
    }:
        candidates.sort(
            key=lambda item: (item[1], item[0], -item[2]),
            reverse=True,
        )
    else:
        candidates.sort(
            key=lambda item: (item[0], item[1], -item[2]),
            reverse=True,
        )
    best_score, _, best_start, best_end, best_window = candidates[0]

    if best_score <= 0:
        return ""

    return best_window


def _page_score(page: Dict[str, Any], topic_id: str, context: Optional[Dict[str, Any]] = None) -> int:
    url = str(page.get("final_url") or page.get("url") or "").lower()
    title = str(page.get("title") or "").lower()
    text = str(page.get("text") or "").lower()
    terms = _topic_terms(topic_id)
    strong = _strong_terms(topic_id)

    score = 0

    if any(fragment in url for fragment in TOPIC_EXCLUDED_PATH_FRAGMENTS.get(topic_id, ())):
        return 0

    strong_present = any(term.lower() in text for term in strong)
    if topic_id in TOPICS_REQUIRING_STRONG_EVIDENCE and not strong_present:
        return 0

    for term in terms:
        term_lower = term.lower()
        if term_lower in title:
            score += 5
        if term_lower in url:
            score += 5
        if term_lower in text:
            score += 2

    for term in strong:
        term_lower = term.lower()
        if term_lower in title:
            score += 10
        if term_lower in url:
            score += 10
        if term_lower in text:
            score += 8

    for hint in TOPIC_PATH_HINTS.get(topic_id, ()):
        if hint in url:
            score += 8

    if context:
        target_degree = _normalise_degree(context.get("target_degree") or context.get("catalog_degree"))
        page_degrees = _page_degrees(page)
        if target_degree and target_degree in page_degrees:
            score += 12

    # Exact-value bonuses make detailed requirements outrank generic overview
    # pages when both mention the same topic.
    if topic_id == "programme_start":
        if "start every semester" in text or "starts every semester" in text:
            score += 45
        if "start of studies" in text or "next intake" in text or "next intakes" in text:
            score += 30
        if "summer semester" in text or "winter semester" in text:
            score += 20
    elif topic_id == "programme_duration":
        if "regelstudienzeit" in text:
            score += 45
        if re.search(r"\bduration\b.{0,80}\b\d+\s+semesters?\b", text):
            score += 40
        if re.search(r"\b\d+\s+semesters?\b", text):
            score += 25
    elif topic_id == "study_format":
        if any(phrase in text for phrase in (
            "online learning",
            "online participation",
            "simultaneously streamed",
            "interactive video conference",
            "interactive video conferences",
        )):
            score += 35
    elif topic_id == "english_language_requirements":
        if re.search(r"\b(toefl|ielts|pte|toeic)\b", text):
            score += 25
        if re.search(r"\b(b2|c1|c2)\b", text):
            score += 15
    elif topic_id == "application_before_graduation":
        if "final semester" in text or "before graduation" in text:
            score += 20
    elif topic_id == "final_certificate_submission":
        if "final degree certificate" in text or "certified official copies" in text:
            score += 20
    elif topic_id == "application_fee":
        # Do not reward tuition/semester-fee language for application-fee
        # questions.  Only explicit application/processing/handling terms count.
        if any(term in text for term in ("application fee", "processing fee", "processing costs", "handling fee", "uni-assist fee")):
            score += 25
    elif topic_id == "tuition_fees":
        if "tuition" in text:
            score += 25
    elif topic_id == "semester_contribution":
        if "semester contribution" in text or "semester fee" in text or "semesterbeitrag" in text:
            score += 25

    return score


def _catalogue_identity_doc(
    context: Dict[str, Any],
    topic_id: str,
) -> Optional[Dict[str, Any]]:
    """Build citable identity evidence from the canonical HTW degree index.

    This document is emitted only when the programme catalogue itself was built
    from a traceable official source URL.  It is intentionally limited to
    identity-level facts (degree, teaching language, study type/format, standard
    duration).  Admission rules, deadlines, fees, documents and test thresholds
    still have to come from programme/application pages or normal retrieval.
    """
    source_url = str(context.get("catalog_source_url") or "").strip()
    if not source_url:
        return None

    programme = str(
        context.get("target_program")
        or context.get("matched_programme")
        or context.get("target_programme")
        or ""
    ).strip()
    programme_id = str(context.get("programme_id") or programme).strip()
    degree = str(
        context.get("catalog_degree_title")
        or context.get("catalog_degree")
        or context.get("target_degree")
        or ""
    ).strip()
    language = str(context.get("catalog_language") or "").strip()
    study_type = str(context.get("catalog_study_type") or "").strip()
    study_format = str(context.get("catalog_study_format") or "").strip()
    study_mode_official = str(context.get("catalog_study_mode_official") or "").strip()
    start_semesters = context.get("catalog_start_semesters") or []
    if not isinstance(start_semesters, list):
        start_semesters = []
    start_semesters = [str(value).strip() for value in start_semesters if str(value).strip()]
    duration = context.get("catalog_duration_semesters")
    retrieved_at = str(context.get("catalog_retrieved_at") or "").strip()

    if topic_id == "language_of_instruction":
        if not language:
            return None
        fact_lines = [f"Teaching language: {language}."]
    elif topic_id == "study_format":
        if not (study_type or study_format or study_mode_official):
            return None
        fact_lines = []
        if study_type:
            fact_lines.append(f"Study type: {study_type}.")
        if study_mode_official:
            fact_lines.append(
                f"Official HTW study classification: {study_mode_official}."
            )
        elif study_format:
            fact_lines.append(f"Official HTW study classification: {study_format}.")
        fact_lines.append(
            "This administrative classification does not by itself establish whether online or hybrid lecture participation is also available."
        )
    elif topic_id == "programme_duration":
        if duration in (None, ""):
            return None
        fact_lines = [f"Standard duration: {duration} semesters."]
    elif topic_id == "programme_overview":
        fact_lines = []
        if degree:
            fact_lines.append(f"Qualification/degree: {degree}.")
        if language:
            fact_lines.append(f"Teaching language: {language}.")
        if study_type:
            fact_lines.append(f"Study type: {study_type}.")
        if study_mode_official:
            fact_lines.append(f"Official HTW study classification: {study_mode_official}.")
        elif study_format:
            fact_lines.append(f"Official HTW study classification: {study_format}.")
        if start_semesters:
            fact_lines.append("Official start semester(s): " + ", ".join(start_semesters) + ".")
        if duration not in (None, ""):
            fact_lines.append(f"Standard duration: {duration} semesters.")
        if not fact_lines:
            return None
    else:
        return None

    content = " ".join(
        [f"Programme: {programme}."]
        + fact_lines
    ).strip()

    return {
        "id": f"official_degree_index::{programme_id}::{topic_id}",
        "title": f"HTW Berlin degree programme index - {programme}",
        "content": content,
        "chunk_text": content,
        "source_url": source_url,
        "url": source_url,
        "object_type": "official_degree_index",
        "object_id": programme_id,
        "score": 1.0,
        "official_evidence_score": 1000,
        "last_updated": retrieved_at,
        "metadata": {
            "program_name": programme,
            "programme_ids": [programme_id] if programme_id else [],
            "degree": _normalise_degree(context.get("catalog_degree") or context.get("target_degree")),
            "topic_id": topic_id,
            "retrieved_at": retrieved_at,
            "source": "official_degree_index",
        },
    }



def _catalogue_start_identity_docs(
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build one citable HTW-index evidence document per supported start semester."""
    programme = str(
        context.get("target_program")
        or context.get("matched_programme")
        or context.get("target_programme")
        or ""
    ).strip()
    programme_id = str(context.get("programme_id") or programme).strip()
    retrieved_at = str(context.get("catalog_retrieved_at") or "").strip()
    semesters = context.get("catalog_start_semesters") or []
    sources = context.get("catalog_start_semester_sources") or {}
    if not isinstance(semesters, list) or not semesters:
        return []
    if not isinstance(sources, dict):
        sources = {}

    docs: List[Dict[str, Any]] = []
    fallback_source = str(context.get("catalog_source_url") or "").strip()
    for semester in semesters:
        label = str(semester or "").strip()
        if not label:
            continue
        source_url = str(sources.get(label) or fallback_source).strip()
        if not source_url:
            continue
        source_is_degree_index = (
            "www.htw-berlin.de" in source_url.lower()
            and "/studium/stg2" in source_url.lower()
        )
        if source_is_degree_index:
            content = (
                f"Programme: {programme}. "
                f"Official HTW degree-index start-semester filter: {label}."
            )
            title = f"HTW Berlin degree programme index - {programme} - {label}"
            object_type = "official_degree_index"
            metadata_source = "official_degree_index"
            id_prefix = "official_degree_index"
        else:
            content = (
                f"Programme: {programme}. "
                f"Official HTW programme page confirms start semester: {label}."
            )
            title = f"Official HTW programme start - {programme} - {label}"
            object_type = "official_programme_page_identity"
            metadata_source = "official_programme_page"
            id_prefix = "official_programme_page_identity"

        slug = "summer" if "summer" in label.lower() else "winter" if "winter" in label.lower() else _normalise(label)
        docs.append(
            {
                "id": f"{id_prefix}::{programme_id}::programme_start::{slug}",
                "title": title,
                "content": content,
                "chunk_text": content,
                "source_url": source_url,
                "url": source_url,
                "object_type": object_type,
                "object_id": programme_id,
                "score": 1.0,
                "official_evidence_score": 1000,
                "last_updated": retrieved_at,
                "metadata": {
                    "program_name": programme,
                    "programme_ids": [programme_id] if programme_id else [],
                    "degree": _normalise_degree(context.get("catalog_degree") or context.get("target_degree")),
                    "topic_id": "programme_start",
                    "start_semester": label,
                    "retrieved_at": retrieved_at,
                    "source": metadata_source,
                },
            }
        )
    return docs

def get_official_programme_docs(
    context: Dict[str, Any],
    topic_id: str,
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Return relevant, degree-compatible programme-page evidence documents."""
    if not context.get("target_program") and not context.get("matched_programme"):
        return []

    identity_docs = (
        _catalogue_start_identity_docs(context)
        if topic_id == "programme_start"
        else []
    )
    if topic_id != "programme_start":
        identity_doc = _catalogue_identity_doc(context, topic_id)
        if identity_doc:
            identity_docs = [identity_doc]

    cache = _deduplicate_pages(_load_cache())
    if not cache:
        return identity_docs[: max(1, limit)]

    matching_pages = [page for page in cache if _programme_matches_page(context, page)]
    if not matching_pages:
        return identity_docs[: max(1, limit)]

    scored = [(page, _page_score(page, topic_id, context)) for page in matching_pages]
    scored.sort(key=lambda item: item[1], reverse=True)

    # No "first three pages" fallback.  A zero-score page does not contain
    # topic evidence and should not be presented as if it did.
    selected = [(page, score) for page, score in scored if score > 0][: max(1, limit)]
    if not selected:
        return identity_docs[: max(1, limit)]

    terms = _topic_terms(topic_id)
    docs: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    for page, page_score in selected:
        text = str(page.get("text") or "")
        snippet = _find_best_snippet(
            text,
            terms,
            topic_id=topic_id,
            max_chars=2600,
        )
        if not snippet:
            continue

        url = str(page.get("final_url") or page.get("url") or "")
        canonical = _canonical_url(url)
        if not canonical or canonical in seen_urls:
            continue
        seen_urls.add(canonical)

        programme_names = _page_programme_names(page)
        programme_ids = _page_programme_ids(page)
        degrees = sorted(_page_degrees(page))
        program_name = (
            page.get("program_name")
            or page.get("programme_name")
            or (programme_names[0] if programme_names else "")
        )
        retrieved_at = page.get("retrieved_at") or page.get("last_updated") or ""

        docs.append(
            {
                "id": f"official_programme_page::{program_name}::{canonical}::{topic_id}",
                "title": page.get("title") or program_name or "Official programme page",
                "content": snippet,
                "chunk_text": snippet,
                "source_url": url,
                "url": url,
                "object_type": "official_programme_page_cache",
                "object_id": programme_ids[0] if programme_ids else (program_name or canonical),
                "score": 1.0,
                "official_evidence_score": page_score,
                "last_updated": str(retrieved_at or ""),
                "metadata": {
                    "program_name": program_name,
                    "program_names": programme_names,
                    "programme_ids": programme_ids,
                    "degree": degrees[0] if len(degrees) == 1 else "",
                    "degrees": degrees,
                    "topic_id": topic_id,
                    "retrieved_at": retrieved_at,
                    "source": "official_programme_page_cache",
                },
            }
        )

    # For duration, a direct programme-page statement is stronger than the
    # generic catalogue duration because joint/cooperation routes can differ.
    # Use the catalogue identity only when no programme-specific duration
    # evidence was found.
    if topic_id == "programme_duration":
        if docs:
            return docs[: max(1, limit)]
        return identity_docs[: max(1, limit)]

    if identity_docs:
        docs = identity_docs + docs

    # Keep the configured source cap after adding canonical identity evidence.
    return docs[: max(1, limit)]
