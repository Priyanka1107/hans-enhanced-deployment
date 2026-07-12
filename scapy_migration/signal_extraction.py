"""
Lightweight signal extraction for embedding-time enrichment.
Extracts retrieval hints from cleaned text without schema population.
"""

import re
from typing import List, Optional, Dict


def extract_euro_amounts(text: str) -> List[str]:
    """
    Extract EUR amounts with European formatting.

    Patterns:
    - 350.00€, €350, 350,00 EUR, 350 EUR, etc.
    """
    amounts = set()

    # Pattern 1: €X or X€
    pattern1 = r'€\s*(\d{1,6}(?:[.,]\d{2})?)'
    for match in re.finditer(pattern1, text):
        amounts.add(match.group(1))

    pattern2 = r'(\d{1,6}(?:[.,]\d{2})?)\s*€'
    for match in re.finditer(pattern2, text):
        amounts.add(match.group(1))

    # Pattern 3: X EUR or X Euro
    pattern3 = r'(\d{1,6}(?:[.,]\d{2})?)\s*(?:EUR|Euro|euros)'
    for match in re.finditer(pattern3, text, re.IGNORECASE):
        amounts.add(match.group(1))

    return sorted(list(amounts))[:10]  # Limit to 10 most common


def extract_date_ranges(text: str) -> List[str]:
    """
    Extract date ranges and deadlines.

    Patterns:
    - DD.MM.YYYY
    - DD.MM.-DD.MM.
    - Month DD, YYYY
    - Xth Month
    """
    dates = []

    # Pattern 1: DD.MM.-DD.MM. (German range)
    pattern1 = r'\b\d{1,2}\.\d{1,2}\.\s*[-–—]\s*\d{1,2}\.\d{1,2}\.'
    dates.extend(re.findall(pattern1, text))

    # Pattern 2: DD.MM.YYYY or DD.MM.
    pattern2 = r'\b\d{1,2}\.\d{1,2}\.(?:\d{4}|\d{2})?'
    dates.extend(re.findall(pattern2, text))

    # Pattern 3: Month DD or DDth Month
    pattern3 = r'\b(?:\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)?)\b'
    dates.extend(re.findall(pattern3, text, re.IGNORECASE))

    # Deduplicate and limit
    seen = set()
    unique_dates = []
    for d in dates:
        normalized = d.strip().lower()
        if normalized not in seen and len(unique_dates) < 8:
            seen.add(normalized)
            unique_dates.append(d.strip())

    return unique_dates


def extract_key_actions(text: str) -> List[str]:
    """
    Extract key action sentences using modal verbs.

    Looks for sentences with: must, need to, required to, should, have to
    """
    actions = []

    # Split into sentences
    sentences = re.split(r'[.!?]+', text)

    modal_verbs = ['must', 'need to', 'required to', 'should', 'have to', 'necessary to']

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 20 or len(sentence) > 200:
            continue

        sentence_lower = sentence.lower()
        if any(modal in sentence_lower for modal in modal_verbs):
            # Clean up
            sentence = re.sub(r'\s+', ' ', sentence)
            actions.append(sentence)

            if len(actions) >= 8:
                break

    return actions


def extract_required_documents(text: str) -> List[str]:
    """
    Extract required documents from lists or headings.

    Looks for:
    - "Which documents are required?"
    - "Required documents:"
    - Bullet lists with document names
    """
    documents = []

    # Find section about required documents
    pattern = r'(?:Which documents|Required documents|Documents required|Application documents)[^\n]*[:?]?\s*((?:[^\n]+\n?){0,15})'
    matches = re.finditer(pattern, text, re.IGNORECASE)

    for match in matches:
        section = match.group(1)

        # Extract lines that look like document items
        lines = section.split('\n')
        for line in lines:
            line = line.strip()

            # Skip very short or very long lines
            if len(line) < 10 or len(line) > 120:
                continue

            # Look for document-like terms
            doc_terms = ['certificate', 'proof', 'copy', 'transcript', 'form', 'card',
                        'document', 'letter', 'application', 'insurance', 'passport']

            if any(term in line.lower() for term in doc_terms):
                # Clean up
                line = re.sub(r'^[-•*]\s*', '', line)
                line = re.sub(r'\s+', ' ', line)
                documents.append(line)

                if len(documents) >= 10:
                    break

        if documents:
            break  # Only process first matching section

    return documents


def extract_eligibility_cues(text: str) -> List[str]:
    """
    Extract eligibility/requirements sentences.

    Looks for sentences with: eligible, requirements, must, can apply, qualify
    """
    cues = []

    sentences = re.split(r'[.!?]+', text)

    eligibility_terms = ['eligible', 'eligibility', 'requirements', 'required',
                        'can apply', 'may apply', 'qualify', 'qualification']

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 25 or len(sentence) > 180:
            continue

        sentence_lower = sentence.lower()
        if any(term in sentence_lower for term in eligibility_terms):
            sentence = re.sub(r'\s+', ' ', sentence)
            cues.append(sentence)

            if len(cues) >= 8:
                break

    return cues


def extract_program_facts(text: str) -> Dict[str, Optional[str]]:
    """
    Extract basic program facts: language, intake, ECTS, duration.
    """
    facts = {
        'language': None,
        'intake': None,
        'ects': None,
        'duration': None
    }

    text_lower = text.lower()

    # Language detection
    if 'taught in english' in text_lower or 'english-taught' in text_lower or 'english language' in text_lower:
        facts['language'] = 'English'
    elif 'b2 english' in text_lower or 'c1 english' in text_lower:
        facts['language'] = 'English'
    elif 'taught in german' in text_lower or 'german-taught' in text_lower:
        facts['language'] = 'German'
    elif 'b2 german' in text_lower or 'c1 german' in text_lower:
        facts['language'] = 'German'

    # Intake detection
    if 'winter semester' in text_lower and 'summer semester' in text_lower:
        facts['intake'] = 'winter+summer'
    elif 'winter semester' in text_lower or 'starts in winter' in text_lower:
        facts['intake'] = 'winter'
    elif 'summer semester' in text_lower or 'starts in summer' in text_lower:
        facts['intake'] = 'summer'

    # ECTS detection
    ects_match = re.search(r'(\d{2,3})\s*ECTS', text)
    if ects_match:
        facts['ects'] = ects_match.group(1)

    # Duration detection
    duration_match = re.search(r'(\d)\s*semester', text_lower)
    if duration_match:
        facts['duration'] = duration_match.group(1) + ' semesters'

    return facts


def build_signal_block(obj: dict, cleaned_full_text: str) -> str:
    """
    Build type-specific signal block for embedding enrichment.

    Args:
        obj: The object dict with metadata and content
        cleaned_full_text: Cleaned full text to extract from

    Returns:
        Formatted signal block string (may be empty)
    """
    object_type = obj.get('metadata', {}).get('object_type', '')

    if not cleaned_full_text:
        return ""

    signal_parts = []

    if object_type == 'application_process':
        # Extract deadlines
        dates = extract_date_ranges(cleaned_full_text)
        if dates:
            signal_parts.append(f"Deadlines mentioned: {', '.join(dates)}")

        # Extract key actions
        actions = extract_key_actions(cleaned_full_text)
        if actions:
            actions_str = ' | '.join(actions[:8])
            signal_parts.append(f"Key actions: {actions_str}")

        # Extract required documents
        docs = extract_required_documents(cleaned_full_text)
        if docs:
            docs_str = '; '.join(docs[:10])
            signal_parts.append(f"Required documents: {docs_str}")

    elif object_type == 'fees_funding_rule':
        # Extract amounts
        amounts = extract_euro_amounts(cleaned_full_text)
        if amounts:
            signal_parts.append(f"Amounts mentioned: {', '.join(amounts)} EUR")

        # Extract eligibility cues
        cues = extract_eligibility_cues(cleaned_full_text)
        if cues:
            cues_str = ' | '.join(cues[:8])
            signal_parts.append(f"Eligibility cues: {cues_str}")

    elif object_type == 'degree_program':
        # Extract program facts
        facts = extract_program_facts(cleaned_full_text)
        fact_strs = []
        for key, value in facts.items():
            if value:
                fact_strs.append(f"{key}={value}")

        if fact_strs:
            signal_parts.append(f"Program facts: {', '.join(fact_strs)}")

    # For other types, skip signal block for now

    if signal_parts:
        return '\n'.join(signal_parts)

    return ""
