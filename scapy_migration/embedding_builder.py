"""
Build enriched embedding text for each scapy object.
"""

from typing import Dict, Optional
from text_cleaning import clean_full_text, is_thin
from signal_extraction import build_signal_block


def build_embedding_text(obj: dict, obj_by_id: Dict[str, dict]) -> tuple[str, dict]:
    """
    Build enriched embedding text from object.

    Args:
        obj: The object dict
        obj_by_id: Map of all objects by ID for enrichment

    Returns:
        Tuple of (embedding_text, enrichment_info)
        enrichment_info contains: enriched (bool), related_obj_used (str or None)
    """
    metadata = obj.get('metadata', {})
    content = obj.get('content', {})

    # Section 1: Identity
    identity_lines = [
        f"Object type: {metadata.get('object_type', 'unknown')}",
        f"Object id: {metadata.get('object_id', 'unknown')}",
        f"Title: {metadata.get('title', '')}",
        f"URL: {metadata.get('url', '')}",
    ]

    classification_notes = metadata.get('classification_notes', '')
    if classification_notes:
        identity_lines.append(f"Classification notes: {classification_notes}")

    identity_block = '\n'.join(identity_lines)

    # Clean full text
    raw_full_text = content.get('full_text', '')
    cleaned_full_text = clean_full_text(raw_full_text)

    # Section 2: Type-specific signal block
    signal_block = build_signal_block(obj, cleaned_full_text)

    # Section 3: Related pages
    related_pages = obj.get('related_pages', [])
    related_block = ""
    if related_pages:
        related_str = ', '.join(related_pages[:10])  # Limit to 10
        related_block = f"Related pages: {related_str}"

    # Section 4: Full text
    full_text_block = f"Full text:\n{cleaned_full_text}"

    # Combine sections
    sections = [identity_block]
    if signal_block:
        sections.append(signal_block)
    if related_block:
        sections.append(related_block)
    sections.append(full_text_block)

    embedding_text = '\n\n'.join(sections)

    # Track enrichment info
    enrichment_info = {
        'enriched': False,
        'related_obj_used': None,
        'cleaned_full_text_len': len(cleaned_full_text),
        'embedding_text_len_before': len(embedding_text),
        'embedding_text_len_after': len(embedding_text),
        'still_thin': False
    }

    # Section 5: Thin hub enrichment
    if is_thin(embedding_text, cleaned_full_text) and related_pages:
        # Find best related object to borrow from
        best_related_obj = select_best_related_object(
            obj, related_pages, obj_by_id
        )

        if best_related_obj:
            # Borrow content
            related_content = extract_related_content_excerpt(
                best_related_obj, obj_by_id
            )

            if related_content:
                related_obj_id = best_related_obj.get('metadata', {}).get('object_id', 'unknown')
                enrichment_block = f"\nRelated content excerpt from {related_obj_id}:\n{related_content}"
                embedding_text += enrichment_block

                enrichment_info['enriched'] = True
                enrichment_info['related_obj_used'] = related_obj_id
                enrichment_info['embedding_text_len_after'] = len(embedding_text)

        # Re-check thinness after enrichment
        enrichment_info['still_thin'] = is_thin(embedding_text, cleaned_full_text + (related_content if enrichment_info['enriched'] else ''))

    return embedding_text, enrichment_info


def select_best_related_object(
    obj: dict,
    related_pages: list,
    obj_by_id: Dict[str, dict]
) -> Optional[dict]:
    """
    Select best related object to borrow content from.

    Priority:
    1. Same object_type
    2. Longest cleaned_full_text
    3. Exclude overview_navigation if possible
    """
    obj_type = obj.get('metadata', {}).get('object_type', '')

    candidates = []
    for related_id in related_pages:
        if related_id not in obj_by_id:
            continue

        related_obj = obj_by_id[related_id]
        related_type = related_obj.get('metadata', {}).get('object_type', '')
        related_text = related_obj.get('content', {}).get('full_text', '')

        # Skip if also thin
        if len(related_text) < 400:
            continue

        # Score candidates
        score = len(related_text)

        # Bonus for same type
        if related_type == obj_type:
            score += 10000

        # Penalty for overview_navigation
        if related_type == 'overview_navigation':
            score -= 5000

        candidates.append((score, related_obj))

    if not candidates:
        return None

    # Return highest scored
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def extract_related_content_excerpt(
    related_obj: dict,
    obj_by_id: Dict[str, dict]
) -> str:
    """
    Extract excerpt from related object.

    Takes first 1200-2000 chars of cleaned embedding_text or full_text.
    """
    # Try to get its embedding text (if already built)
    # For simplicity, just use cleaned full_text
    related_full_text = related_obj.get('content', {}).get('full_text', '')
    cleaned = clean_full_text(related_full_text)

    if not cleaned:
        return ""

    # Take first 1200-2000 chars, trying to break at sentence
    target_len = min(len(cleaned), 2000)
    excerpt = cleaned[:target_len]

    # Try to end at sentence boundary
    if target_len < len(cleaned):
        last_period = excerpt.rfind('. ')
        if last_period > 1000:  # Only if we have enough content
            excerpt = excerpt[:last_period + 1]

    return excerpt.strip()
