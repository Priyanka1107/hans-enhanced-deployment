from __future__ import annotations

import re
from typing import Any, Dict, List


_ATTACHMENT_REFERENCE_PATTERNS = (
    r"\battached\b",
    r"\battachment\b",
    r"\bsee\s+(?:the\s+)?attached\b",
    r"\bi\s+have\s+attached\b",
    r"\bin\s+the\s+attachment\b",
    r"\banbei\b",
    r"\bim\s+anhang\b",
    r"\banhang\b",
    r"\bbeigef(?:ü|ue)gt\b",
)


def _mentions_unavailable_attachment(
    email_text: str,
) -> bool:
    return any(
        re.search(
            pattern,
            email_text or "",
            flags=re.IGNORECASE,
        )
        for pattern in _ATTACHMENT_REFERENCE_PATTERNS
    )


def build_manual_verification_reasons(
    *,
    email_text: str,
    email_context: Dict[str, Any],
) -> List[str]:
    """
    Return concrete staff-review reasons that HANS can determine reliably.

    These checks describe limitations of the current request data. They do not
    attempt to infer whether an email is generally "complex", which would be
    subjective and harder to test or explain.
    """
    reasons: List[str] = []

    if _mentions_unavailable_attachment(
        email_text
    ):
        reasons.append(
            "Manual verification required: the enquiry refers to "
            "an attachment or supporting document that HANS has "
            "not inspected."
        )

    if bool(
        email_context.get(
            "catalog_degree_ambiguous",
            False,
        )
    ):
        reasons.append(
            "Manual verification required: the programme degree "
            "level is ambiguous; staff should confirm the "
            "applicable Bachelor/Master route."
        )

    return reasons
