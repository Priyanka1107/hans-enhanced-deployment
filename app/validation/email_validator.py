from __future__ import annotations

import re
from typing import Any, Dict, List


def extract_citation_numbers(text: str) -> List[int]:
    citations: List[int] = []

    for match in re.finditer(
        r"\[Doc\s*(\d+)\]",
        text or "",
        flags=re.IGNORECASE,
    ):
        number = int(match.group(1))

        if number not in citations:
            citations.append(number)

    return citations


def validate_email_draft(
    *,
    draft: str,
    documents: List[Dict[str, Any]],
    topics: List[Dict[str, Any]],
    email_context: Dict[str, Any],
) -> Dict[str, Any]:
    reasons: List[str] = []

    citation_numbers = extract_citation_numbers(draft)

    citations_valid = bool(citation_numbers) and all(
        1 <= number <= len(documents)
        for number in citation_numbers
    )

    if not topics:
        reasons.append("No topics detected")

    if not documents:
        reasons.append("No evidence documents retrieved")

    if not citation_numbers:
        reasons.append("No citations in draft")

    if citation_numbers and not citations_valid:
        reasons.append("Draft contains invalid citation numbers")

    programme_specific_topics = {
        "application_deadline",
        "admission_requirements",
        "required_documents",
        "english_language_requirements",
        "german_language_requirements",
        "language_of_instruction",
        "study_format",
        "work_experience",
        "motivation_letter",
        "application_before_graduation",
    }

    topic_ids = {
        str(topic.get("topic_id", ""))
        for topic in topics
    }

    if (
        topic_ids & programme_specific_topics
        and not email_context.get("target_program")
    ):
        reasons.append(
            "Programme-specific question but programme was not confidently matched"
        )

    unsupported_phrases = [
        "you are eligible",
        "you will definitely be admitted",
        "your admission is guaranteed",
        "you do not need to verify",
    ]

    lower_draft = (draft or "").lower()

    if any(
        phrase in lower_draft
        for phrase in unsupported_phrases
    ):
        reasons.append(
            "Draft contains an unsupported eligibility or admission statement"
        )

    is_grounded = bool(
        documents
        and citation_numbers
        and citations_valid
    )

    confidence = 0.0

    if documents:
        confidence += 0.35

    if topics:
        confidence += 0.20

    if citation_numbers:
        confidence += 0.25

    if citations_valid:
        confidence += 0.20

    confidence = min(confidence, 1.0)

    review_required = bool(reasons)

    return {
        "is_grounded": is_grounded,
        "citations_valid": citations_valid,
        "has_hallucinations": any(
            "unsupported" in reason.lower()
            for reason in reasons
        ),
        "confidence": confidence,
        "failure_type": (
            "manual_review_required"
            if review_required
            else None
        ),
        "review_required": review_required,
        "review_reason": "; ".join(reasons),
        "citation_count": len(citation_numbers),
        "citations": [
            f"[Doc {number}]"
            for number in citation_numbers
        ],
    }