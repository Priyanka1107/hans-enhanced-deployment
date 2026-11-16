from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal


ScopeRoute = Literal["HANS", "REVIEW", "SKIP"]


@dataclass(frozen=True)
class ScopeDecision:
    """Deterministic routing decision made before retrieval or generation."""

    route: ScopeRoute
    reason: str


_HANS_PATTERNS = (
    r"\bapplication\b",
    r"\bapply\b",
    r"\badmission\b",
    r"\bdeadline\b",
    r"\buni[- ]?assist\b",
    r"\bvpd\b",
    r"\bprogramme\b",
    r"\bprogram\b",
    r"\bbachelor(?:'s)?\b",
    r"\bmaster(?:'s)?\b",
    r"\bcredit\s+(?:transfer|recognition)\b",
    r"\btransfer\s+(?:student|credits?)\b",
    r"\bqualification\s+recognition\b",
    r"\blanguage\s+(?:requirement|proof|certificate)\b",
    r"\bproof\s+of\s+english\b",
    r"\benglish\s+(?:proficiency|requirement|requirements)\b",
    r"\bgerman\s+(?:proficiency|requirement|requirements)\b",
    r"\bdocuments?\b",
    r"\btoefl\b",
    r"\bielts\b",
    r"\benrol(?:l)?ment\b",
    r"\bre[- ]?registration\b",
    r"\bbewerbung\b",
    r"\bbewerbungsfrist\b",
    r"\bzulassung\b",
    r"\bunterlagen\b",
    r"\bstudiengang\b",
    r"\bsprachnachweis\b",
    r"\banerkennung\b",
)

_CLEAR_OUT_OF_SCOPE_PATTERNS = (
    r"\bmensa\b",
    r"\bcafeteria\b",
    r"\bcanteen\b",
    r"\bmeal\s+(?:plan|menu)\b",
    r"\blunch\s+menu\b",
    r"\bspeiseplan\b",
)


def _matches_any(
    text: str,
    patterns: tuple[str, ...],
) -> bool:
    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for pattern in patterns
    )


def classify_email_scope(
    *,
    subject: str = "",
    email_text: str,
) -> ScopeDecision:
    """
    Classify an email before HANS retrieval and model generation.

    The router is intentionally conservative:
    - HANS: a supported Student Services/admissions signal is present.
    - SKIP: a clearly out-of-scope signal is present and no HANS signal exists.
    - REVIEW: the email is not clearly supported or clearly out of scope.

    REVIEW prevents uncertain messages from being silently discarded.
    """
    combined_text = " ".join(
        part.strip()
        for part in (
            subject or "",
            email_text or "",
        )
        if part and part.strip()
    )

    if _matches_any(
        combined_text,
        _HANS_PATTERNS,
    ):
        return ScopeDecision(
            route="HANS",
            reason=(
                "Supported HANS Student Services topic detected."
            ),
        )

    if _matches_any(
        combined_text,
        _CLEAR_OUT_OF_SCOPE_PATTERNS,
    ):
        return ScopeDecision(
            route="SKIP",
            reason=(
                "Enquiry appears outside the currently supported "
                "HANS Student Services scope."
            ),
        )

    return ScopeDecision(
        route="REVIEW",
        reason=(
            "Enquiry could not be confidently classified as a "
            "supported HANS Student Services topic."
        ),
    )
