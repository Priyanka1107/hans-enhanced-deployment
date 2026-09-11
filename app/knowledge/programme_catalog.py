"""
Canonical programme catalogue utilities for the HANS email assistant.

The catalogue contains programme identity and programme metadata only.  It must
not contain admission facts such as deadlines, language test scores or fees.
Those facts come from retrieved official evidence.

Matching principles:
- prefer exact name/alias matches;
- use the target degree explicitly stated by the student to disambiguate a
  programme that exists at both Bachelor and Master level;
- never choose an arbitrary degree variant merely because it appears first in
  the JSON file;
- if the programme name is clear but the degree is ambiguous, return the
  programme identity with ``degree=None`` rather than guessing;
- fuzzy matching remains conservative and is only a fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse
import difflib
import json
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG_PATH = PROJECT_ROOT / "data" / "programme_catalog.json"


@dataclass
class ProgrammeMatch:
    name: str
    aliases: List[str]
    degree: Optional[str] = None
    degree_title: Optional[str] = None
    language: Optional[str] = None
    study_format: Optional[str] = None
    study_type: Optional[str] = None
    study_mode_official: Optional[str] = None
    duration_semesters: Optional[int] = None
    start_semesters: List[str] = field(default_factory=list)
    start_semester_sources: Dict[str, str] = field(default_factory=dict)
    url: Optional[str] = None
    application_url: Optional[str] = None
    programme_id: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    score: float = 0.0
    source: str = "catalog"
    ambiguous_degree: bool = False

    def to_context_fields(self) -> Dict[str, Any]:
        fields: Dict[str, Any] = {
            "target_program": self.name,
            "target_program_url": self.url,
            "target_program_application_url": self.application_url,
            "target_program_match_score": f"{self.score:.2f}",
            "target_program_source": self.source,
            "catalog_degree": self.degree,
            "catalog_language": self.language,
            "catalog_study_format": self.study_format,
        }
        if self.study_mode_official:
            fields["catalog_study_mode_official"] = self.study_mode_official
        if self.start_semesters:
            fields["catalog_start_semesters"] = list(self.start_semesters)
        if self.start_semester_sources:
            fields["catalog_start_semester_sources"] = dict(self.start_semester_sources)
        if self.programme_id:
            fields["programme_id"] = self.programme_id
        if self.source_url:
            fields["catalog_source_url"] = self.source_url
        if self.retrieved_at:
            fields["catalog_retrieved_at"] = self.retrieved_at
        if self.degree_title:
            fields["catalog_degree_title"] = self.degree_title
        if self.study_type:
            fields["catalog_study_type"] = self.study_type
        if self.duration_semesters is not None:
            fields["catalog_duration_semesters"] = self.duration_semesters
        if self.ambiguous_degree:
            fields["catalog_degree_ambiguous"] = True
        return fields


def _normalize(text: Any) -> str:
    value = str(text or "").lower()
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^a-z0-9äöüß]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalise_degree(value: Any) -> str:
    text = _normalize(value)
    if not text or text == "unknown":
        return ""
    if "bachelor" in text:
        return "Bachelor"
    if "master" in text or text == "mba":
        return "Master"
    return ""


def _base_programme_name(name: str) -> str:
    """Remove legacy '(Bachelor)'/'(Master)' suffixes for identity comparison."""
    return re.sub(
        r"\s*\((?:bachelor|master)\)\s*$",
        "",
        str(name or ""),
        flags=re.IGNORECASE,
    ).strip()


def infer_target_degree(text: str) -> str:
    """
    Infer the *target* degree from applicant wording.

    Background education such as "I am completing my Bachelor's degree" is not
    treated as a Bachelor target unless the same sentence expresses intent to
    apply for a Bachelor programme.
    """
    raw = str(text or "")
    lower = raw.lower()
    if not lower:
        return ""

    sentences = re.split(r"(?<=[.!?])\s+|\n+", lower)

    target_verbs = r"apply|applying|application|interested|want|would like|like to|bewerben|bewerbung|interessiere|interessiert|möchte|will"

    for sentence in sentences:
        if re.search(
            rf"(?:{target_verbs}).{{0,120}}(?:master|master's|master’s|masterstudiengang|masterstudium)",
            sentence,
        ) or re.search(
            r"(?:master|master's|master’s).{0,80}(?:programme|program|degree|study programme)",
            sentence,
        ):
            return "Master"

    for sentence in sentences:
        background_bachelor = bool(
            re.search(
                r"(?:completed|completing|finishing|finished|have|hold|holding|currently in|final year|final semester|abgeschlossen|schließe).{0,100}"
                r"(?:bachelor|bachelor's|bachelor’s|bachelorabschluss)",
                sentence,
            )
        )
        target_bachelor = bool(
            re.search(
                rf"(?:{target_verbs}).{{0,120}}(?:bachelor|bachelor's|bachelor’s|bachelorstudiengang|bachelorstudium)",
                sentence,
            )
            or re.search(
                r"(?:bachelor|bachelor's|bachelor’s).{0,80}(?:programme|program|study programme)",
                sentence,
            )
        )
        if target_bachelor and (not background_bachelor or target_bachelor):
            return "Bachelor"

    # Subject-style fragments often omit an intent verb: "International Business Master".
    if re.search(r"\b(master|master's|master’s|masterstudiengang|masterstudium)\b", lower):
        return "Master"

    if re.search(r"\b(bachelorstudiengang|bachelorstudium)\b", lower):
        return "Bachelor"

    return ""


def load_programme_catalog(path: Optional[str] = None) -> List[Dict[str, Any]]:
    catalog_path = Path(path) if path else DEFAULT_CATALOG_PATH
    if not catalog_path.exists():
        return []
    try:
        with catalog_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception:
        return []

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("programmes", "programs", "degree_programmes"):
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _item_aliases(item: Dict[str, Any]) -> List[str]:
    name = str(item.get("program_name") or item.get("programme_name") or item.get("name") or "").strip()
    aliases: List[str] = []
    if name:
        aliases.append(name)
        base = _base_programme_name(name)
        if base and base != name:
            aliases.append(base)
    raw_aliases = item.get("aliases") or []
    if isinstance(raw_aliases, list):
        aliases.extend(str(alias).strip() for alias in raw_aliases if str(alias).strip())
    return list(dict.fromkeys(aliases))


def _match_from_item(
    item: Dict[str, Any],
    *,
    score: float,
    source: str,
    ambiguous_degree: bool = False,
    degree_override: Optional[str] = None,
    url_override: Optional[str] = None,
) -> ProgrammeMatch:
    name = str(item.get("program_name") or item.get("programme_name") or item.get("name") or "").strip()
    degree = degree_override if degree_override is not None else _normalise_degree(item.get("degree"))
    duration = item.get("duration_semesters")
    try:
        duration_int = int(duration) if duration not in (None, "") else None
    except (TypeError, ValueError):
        duration_int = None

    raw_start_semesters = item.get("start_semesters") or []
    start_semesters = (
        [str(value).strip() for value in raw_start_semesters if str(value).strip()]
        if isinstance(raw_start_semesters, list)
        else []
    )
    raw_start_sources = item.get("start_semester_sources") or {}
    start_semester_sources = (
        {str(key).strip(): str(value).strip() for key, value in raw_start_sources.items() if str(key).strip() and str(value).strip()}
        if isinstance(raw_start_sources, dict)
        else {}
    )

    # For a degree-ambiguous programme name, do not leak metadata from whichever
    # Bachelor/Master row happened to sort first.  Only programme identity and a
    # shared root URL are safe until the student's target degree is known.
    if ambiguous_degree:
        return ProgrammeMatch(
            name=_base_programme_name(name) or name,
            aliases=[_base_programme_name(name) or name],
            degree=None,
            degree_title=None,
            language=None,
            study_format=None,
            study_type=None,
            study_mode_official=None,
            duration_semesters=None,
            start_semesters=[],
            start_semester_sources={},
            url=url_override if url_override is not None else None,
            application_url=None,
            programme_id=None,
            source_url=str(item.get("source_url") or "").strip() or None,
            retrieved_at=str(item.get("retrieved_at") or "").strip() or None,
            score=score,
            source=source,
            ambiguous_degree=True,
        )

    return ProgrammeMatch(
        name=_base_programme_name(name) or name,
        aliases=_item_aliases(item),
        degree=degree or None,
        degree_title=str(item.get("degree_title") or "").strip() or None,
        language=str(item.get("language") or "").strip() or None,
        study_format=str(item.get("study_format") or "").strip() or None,
        study_type=str(item.get("study_type") or "").strip() or None,
        study_mode_official=str(item.get("study_mode_official") or "").strip() or None,
        duration_semesters=duration_int,
        start_semesters=start_semesters,
        start_semester_sources=start_semester_sources,
        url=url_override if url_override is not None else (str(item.get("url") or "").strip() or None),
        application_url=str(item.get("application_url") or "").strip() or None,
        programme_id=str(item.get("programme_id") or "").strip() or None,
        source_url=str(item.get("source_url") or "").strip() or None,
        retrieved_at=str(item.get("retrieved_at") or "").strip() or None,
        score=score,
        source=source,
        ambiguous_degree=ambiguous_degree,
    )


def _shared_url(items: Sequence[Dict[str, Any]]) -> Optional[str]:
    urls = [str(item.get("url") or "").strip() for item in items if str(item.get("url") or "").strip()]
    if not urls:
        return None
    hosts = {urlparse(url).netloc.lower().removeprefix("www.") for url in urls}
    if len(hosts) == 1:
        # When Bachelor and Master use the same programme host, the common root
        # is safe as a programme identity URL even if the degree-specific page is
        # discovered later by the page refresh step.
        first = urls[0]
        parsed = urlparse(first)
        return f"{parsed.scheme or 'https'}://{parsed.netloc}".rstrip("/")
    return None


def _resolve_candidates(
    candidates: Sequence[Tuple[Dict[str, Any], float, int]],
    *,
    explicit_degree: str,
    source: str,
) -> Optional[ProgrammeMatch]:
    if not candidates:
        return None

    # Highest score first, then the longest matched alias.  This prevents a short
    # alias embedded in a more specific programme name from winning a tie.
    max_score = max(score for _, score, _ in candidates)
    top = [candidate for candidate in candidates if candidate[1] == max_score]
    max_len = max(length for _, _, length in top)
    top = [candidate for candidate in top if candidate[2] == max_len]

    if explicit_degree:
        matching_degree = [
            candidate
            for candidate in top
            if _normalise_degree(candidate[0].get("degree")) == explicit_degree
        ]
        if matching_degree:
            top = matching_degree
        else:
            neutral = [
                candidate
                for candidate in top
                if not _normalise_degree(candidate[0].get("degree"))
            ]
            if neutral:
                top = neutral
            else:
                # A catalogue that contains only the opposite degree must not
                # override the student's explicit target degree.
                return None

    identities = {
        _normalize(_base_programme_name(str(item.get("program_name") or item.get("name") or "")))
        for item, _, _ in top
    }
    identities.discard("")

    if len(identities) > 1:
        # Truly ambiguous between different programmes: do not guess.
        return None

    if len(top) == 1:
        item, score, _ = top[0]
        return _match_from_item(item, score=score, source=source)

    # If a legacy catalogue contains a degree-neutral base record alongside a
    # degree-specific variant, prefer the neutral record when the student did
    # not state a target degree.  This prevents the old International Business
    # Bachelor row from winning simply because it sorts first.
    if not explicit_degree:
        neutral_top = [
            candidate
            for candidate in top
            if not _normalise_degree(candidate[0].get("degree"))
        ]
        if neutral_top:
            item, score, _ = sorted(
                neutral_top,
                key=lambda candidate: (
                    str(candidate[0].get("programme_id") or ""),
                    str(candidate[0].get("url") or ""),
                ),
            )[0]
            return _match_from_item(
                item,
                score=score,
                source=f"{source}_degree_neutral",
            )

    degrees = {
        degree
        for degree in (_normalise_degree(item.get("degree")) for item, _, _ in top)
        if degree
    }

    if explicit_degree and len(degrees) <= 1:
        item, score, _ = top[0]
        return _match_from_item(item, score=score, source=source)

    if len(degrees) > 1:
        # Programme identity is known, degree variant is not.  Preserve the name
        # and shared host but deliberately leave degree unset.
        item, score, _ = top[0]
        return _match_from_item(
            item,
            score=score,
            source=f"{source}_ambiguous_degree",
            ambiguous_degree=True,
            degree_override="",
            url_override=_shared_url([candidate[0] for candidate in top]),
        )

    # Duplicate equivalent rows: choose deterministically but do not let JSON
    # ordering decide between different degrees (handled above).
    item, score, _ = sorted(
        top,
        key=lambda candidate: (
            str(candidate[0].get("programme_id") or ""),
            str(candidate[0].get("url") or ""),
        ),
    )[0]
    return _match_from_item(item, score=score, source=source)


def match_programme_from_catalog(
    text: str,
    *,
    min_score: float = 0.78,
    target_degree: Optional[str] = None,
) -> Optional[ProgrammeMatch]:
    """Match a programme mentioned in free text without guessing its degree."""
    raw = str(text or "")
    norm_text = _normalize(raw)
    if not norm_text:
        return None

    catalogue = load_programme_catalog()
    if not catalogue:
        return None

    explicit_degree = _normalise_degree(target_degree) or infer_target_degree(raw)

    exact_candidates: List[Tuple[Dict[str, Any], float, int]] = []

    for item in catalogue:
        name = item.get("program_name") or item.get("programme_name") or item.get("name") or ""
        if not str(name).strip():
            continue

        for alias in _item_aliases(item):
            alias_norm = _normalize(alias)
            if not alias_norm:
                continue
            if re.search(rf"(?<![a-z0-9äöüß]){re.escape(alias_norm)}(?![a-z0-9äöüß])", norm_text):
                score = 1.0 if len(alias_norm) > 4 else 0.92
                exact_candidates.append((item, score, len(alias_norm)))

    exact_match = _resolve_candidates(
        exact_candidates,
        explicit_degree=explicit_degree,
        source="scraped_programme_catalogue",
    )
    if exact_match is not None:
        return exact_match

    # Fuzzy fallback for misspellings.  Only multi-word aliases are considered,
    # and degree disambiguation is still applied after scoring.
    tokens = norm_text.split()
    windows: List[str] = []
    for size in range(3, min(9, len(tokens)) + 1):
        for index in range(0, len(tokens) - size + 1):
            windows.append(" ".join(tokens[index:index + size]))

    fuzzy_candidates: List[Tuple[Dict[str, Any], float, int]] = []
    best_fuzzy = 0.0

    for item in catalogue:
        for alias in _item_aliases(item):
            alias_norm = _normalize(alias)
            if len(alias_norm.split()) < 2:
                continue
            for window in windows:
                score = difflib.SequenceMatcher(None, alias_norm, window).ratio()
                if score < min_score:
                    continue
                if score > best_fuzzy:
                    best_fuzzy = score
                    fuzzy_candidates = [(item, score, len(alias_norm))]
                elif abs(score - best_fuzzy) < 1e-9:
                    fuzzy_candidates.append((item, score, len(alias_norm)))

    return _resolve_candidates(
        fuzzy_candidates,
        explicit_degree=explicit_degree,
        source="scraped_programme_catalogue_fuzzy",
    )


def programme_reference_lines(context: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    program = context.get("target_program")
    url = context.get("target_program_url")
    app_url = context.get("target_program_application_url")

    if program and url:
        lines.append(f"- Programme page ({program}): {url}")
    if program and app_url and app_url != url:
        lines.append(f"- Programme application page ({program}): {app_url}")
    return lines


def programme_query_terms(context: Dict[str, Any]) -> str:
    parts: List[str] = []
    if context.get("target_program"):
        parts.append(str(context["target_program"]))
    if context.get("target_program_url"):
        parts.append(str(context["target_program_url"]))
    if context.get("target_program_application_url"):
        parts.append(str(context["target_program_application_url"]))
    degree = _normalise_degree(context.get("catalog_degree"))
    if degree:
        parts.append(f"catalogue degree {degree}")
    if context.get("catalog_language"):
        parts.append(f"catalogue language {context['catalog_language']}")
    if context.get("catalog_study_format"):
        parts.append(
            f"catalogue study classification {context['catalog_study_format']}"
        )
    start_semesters = context.get("catalog_start_semesters") or []
    if isinstance(start_semesters, list) and start_semesters:
        parts.append(
            "catalogue start semesters " + ", ".join(str(value) for value in start_semesters)
        )
    return ". ".join(parts)
