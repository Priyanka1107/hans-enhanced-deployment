"""Programme context bridge used by the HANS email service.

There is intentionally only one catalogue matcher.  Older versions implemented a
second independent matcher here, which could disagree with
``programme_catalog.match_programme_from_catalog``.  This module now delegates to
the canonical matcher and only formats the resulting metadata for retrieval and
generation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.knowledge.programme_catalog import (
    ProgrammeMatch,
    infer_target_degree,
    match_programme_from_catalog,
)


def match_programme(text: str) -> Optional[Dict[str, Any]]:
    """Backward-compatible dict wrapper around the canonical matcher."""
    match = match_programme_from_catalog(text)
    if match is None:
        return None

    return {
        "programme_id": match.programme_id,
        "source_url": match.source_url,
        "retrieved_at": match.retrieved_at,
        "program_name": match.name,
        "aliases": match.aliases,
        "degree": match.degree,
        "degree_title": match.degree_title,
        "language": match.language,
        "study_format": match.study_format,
        "study_type": match.study_type,
        "study_mode_official": match.study_mode_official,
        "duration_semesters": match.duration_semesters,
        "start_semesters": list(match.start_semesters),
        "start_semester_sources": dict(match.start_semester_sources),
        "url": match.url,
        "application_url": match.application_url,
        "score": match.score,
        "source": match.source,
        "ambiguous_degree": match.ambiguous_degree,
    }


def build_programme_context_block(email_text: str, subject: str = "") -> Dict[str, Any]:
    """Build programme identity context without injecting admission facts."""
    combined_text = f"{subject}\n{email_text}".strip()
    explicit_degree = infer_target_degree(combined_text)
    match: Optional[ProgrammeMatch] = match_programme_from_catalog(
        combined_text,
        target_degree=explicit_degree or None,
    )

    if match is None:
        return {
            "matched": False,
            "program_name": "",
            "context_block": "",
            "url": "",
            "application_url": "",
            "degree": explicit_degree,
            "catalogue_degree": "",
            "explicit_degree": explicit_degree,
            "language": "",
            "study_format": "",
            "study_type": "",
            "study_mode_official": "",
            "start_semesters": [],
            "start_semester_sources": {},
            "programme_id": "",
            "source_url": "",
            "retrieved_at": "",
            "ambiguous_degree": False,
        }

    catalogue_degree = str(match.degree or "").strip()
    degree = explicit_degree or catalogue_degree
    alias_text = ", ".join(alias for alias in match.aliases if alias)

    lines = [
        "Known programme identity from the local HTW programme catalogue:",
        f"- Programme name: {match.name}",
    ]

    if match.programme_id:
        lines.append(f"- Programme ID: {match.programme_id}")
    if match.source_url:
        lines.append(f"- Canonical catalogue source: {match.source_url}")
    if alias_text:
        lines.append(f"- Known aliases: {alias_text}")

    if degree:
        if explicit_degree and catalogue_degree and explicit_degree != catalogue_degree:
            lines.append(f"- Degree level stated by the student: {explicit_degree}")
            lines.append(f"- Catalogue degree metadata: {catalogue_degree}")
            lines.append("- The student's explicitly stated target degree is authoritative for this request.")
        else:
            lines.append(f"- Degree level: {degree}")
    elif match.ambiguous_degree:
        lines.append("- Degree level: ambiguous (the programme exists at more than one degree level).")

    if match.degree_title:
        lines.append(f"- Qualification: {match.degree_title}")
    if match.language:
        lines.append(f"- Catalogue language metadata: {match.language}")
    if match.study_type:
        lines.append(f"- Catalogue study type metadata: {match.study_type}")
    if match.study_mode_official:
        lines.append(
            f"- Official HTW study classification: {match.study_mode_official}"
        )
    elif match.study_format:
        lines.append(f"- Catalogue study classification: {match.study_format}")
    if match.start_semesters:
        lines.append(
            "- Official start semester(s): " + ", ".join(match.start_semesters)
        )
    if match.url:
        lines.append(f"- Programme URL: {match.url}")
    if match.application_url:
        lines.append(f"- Programme application URL: {match.application_url}")

    lines.extend(
        [
            "",
            "Important:",
            "- This block contains programme identity/metadata only, not admission facts.",
            "- Official study classification (for example Präsenzstudium) is not the same as actual lecture delivery; online/hybrid attendance must be confirmed from programme-specific evidence.",
            "- Deadlines, language-test thresholds, fees, documents and eligibility rules must come from retrieved official evidence.",
        ]
    )

    return {
        "matched": True,
        "program_name": match.name,
        "matched_programme": match.name,
        "context_block": "\n".join(lines),
        "url": match.url or "",
        "application_url": match.application_url or "",
        "degree": degree,
        "catalogue_degree": catalogue_degree,
        "explicit_degree": explicit_degree,
        "degree_title": match.degree_title or "",
        "language": match.language or "",
        "study_format": match.study_format or "",
        "study_type": match.study_type or "",
        "study_mode_official": match.study_mode_official or "",
        "duration_semesters": match.duration_semesters,
        "start_semesters": list(match.start_semesters),
        "start_semester_sources": dict(match.start_semester_sources),
        "programme_id": match.programme_id or "",
        "source_url": match.source_url or "",
        "retrieved_at": match.retrieved_at or "",
        "ambiguous_degree": match.ambiguous_degree,
        "score": match.score,
        "source": match.source,
    }


def enrich_email_text_with_programme_context(email_text: str, subject: str = "") -> Dict[str, Any]:
    """Return programme metadata plus a legacy enriched-text representation."""
    context = build_programme_context_block(email_text=email_text, subject=subject)

    if not context["matched"]:
        return {**context, "enriched_email_text": email_text}

    enriched_email_text = (
        context["context_block"]
        + "\n\nOriginal student email:\n"
        + str(email_text or "")
    )

    return {**context, "enriched_email_text": enriched_email_text}
