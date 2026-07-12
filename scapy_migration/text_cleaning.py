"""
Text cleaning utilities for scapy object migration.
Removes breadcrumbs, headers, and navigation artifacts while preserving content.
"""

import re
from typing import Optional


def clean_full_text(text: str) -> str:
    """
    Clean full_text by removing common breadcrumb/header noise.

    IMPORTANT FIX: Many objects have full_text as a single long line. We must strip
    header prefixes but NEVER delete the entire content just because it starts
    with the HTW header pattern. Instead, we remove the prefix and keep the remainder.

    Args:
        text: Raw full_text from object

    Returns:
        Cleaned text with normalized whitespace
    """
    if not text:
        return ""

    # CRITICAL FIX: Strip common header prefix from the START of text before line processing
    # Many full_text values are single lines starting with:
    # "HTW Berlin - University of Applied Sciences - studies, research, further education"
    # We must remove this prefix but keep the remainder of the content.
    # Only strip from the beginning of the text, not from every line.
    header_pattern = r'^HTW Berlin - University of Applied Sciences(?:\s*[-–—]\s*(?:studies|research|further education|Studium|Forschung)(?:\s*,\s*(?:studies|research|further education|Studium|Forschung))*\s*)?'
    text = re.sub(header_pattern, '', text, count=1).strip()

    # If after removing header the text is empty, return empty (genuinely no content)
    if not text:
        return ""

    lines = text.split('\n')
    cleaned_lines = []

    # Track if we've seen meaningful content to avoid dropping intro text
    seen_content = False
    title_seen = False

    for line in lines:
        line_stripped = line.strip()

        # Skip empty lines at the start
        if not line_stripped and not seen_content:
            continue

        # Skip navigation breadcrumbs (e.g., "International Pathways to HTW Berlin English-Language Study Programmes")
        # These typically have multiple unrelated capitalized phrases without punctuation
        # ONLY check this for short lines at the beginning to avoid dropping content
        if not seen_content and len(line_stripped) < 150 and len(line_stripped) > 10:
            # Check if it looks like a navigation chain (multiple capital words, few lowercase connectors)
            words = line_stripped.split()
            if len(words) > 2 and len(words) < 15:
                capital_words = sum(1 for w in words if w and w[0].isupper())
                if capital_words / len(words) > 0.6 and line_stripped.count('.') == 0:
                    # Likely breadcrumb
                    continue

        # Skip repeated "Table of contents" headers
        if line_stripped.lower() in ['table of contents', 'quick access', 'further information']:
            continue

        # Mark that we've seen actual content
        if len(line_stripped) > 30 or (line_stripped and not title_seen):
            seen_content = True
            title_seen = True

        cleaned_lines.append(line_stripped)

    # Join and normalize whitespace
    cleaned = ' '.join(cleaned_lines)

    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)

    # Remove excessive spacing around punctuation
    cleaned = re.sub(r'\s+([.,;:!?)])', r'\1', cleaned)
    cleaned = re.sub(r'([(])\s+', r'\1', cleaned)

    return cleaned.strip()


def is_thin(embedding_text: str, cleaned_full_text: str) -> bool:
    """
    Determine if content is too thin for good retrieval.

    Args:
        embedding_text: The constructed embedding text (before enrichment)
        cleaned_full_text: The cleaned full text from object

    Returns:
        True if content is thin and should be enriched
    """
    # Thin if cleaned text is very short
    if len(cleaned_full_text) < 400:
        return True

    # Thin if embedding text (with metadata) is still short
    if len(embedding_text) < 600:
        return True

    # Thin if text appears to be mostly headings/links (low alphanumeric density)
    alphanumeric = sum(c.isalnum() for c in cleaned_full_text)
    if alphanumeric / max(len(cleaned_full_text), 1) < 0.5:
        return True

    # Check if it's mostly short lines (likely navigation/list of links)
    lines = [l.strip() for l in cleaned_full_text.split('.') if l.strip()]
    if len(lines) > 5:
        short_lines = sum(1 for l in lines if len(l) < 80)
        if short_lines / len(lines) > 0.7:
            return True

    return False


def calculate_content_quality(text: str) -> dict:
    """
    Calculate quality metrics for content.

    Returns:
        Dict with length, alphanumeric_ratio, avg_sentence_length
    """
    if not text:
        return {
            'length': 0,
            'alphanumeric_ratio': 0.0,
            'avg_sentence_length': 0
        }

    alphanumeric = sum(c.isalnum() for c in text)
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

    return {
        'length': len(text),
        'alphanumeric_ratio': alphanumeric / len(text) if text else 0.0,
        'avg_sentence_length': len(text) / len(sentences) if sentences else 0
    }
