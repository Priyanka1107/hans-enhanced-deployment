"""
Object Builder Script

Reads page_classification.csv and HTML snapshots to generate structured JSON objects
for the RAG/MCP system.

Usage:
    python build_objects.py

Output:
    Creates objects/ directory with one JSON file per classified page
"""

import csv
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import re

from html_extractor import extract_all, clean_whitespace, extract_email, extract_date


# Configuration
CSV_FILE = Path("outputs/page_classification.csv")
SNAPSHOTS_DIR = Path("snapshots_raw")
OUTPUT_DIR = Path("outputs/objects")
SCRAPE_DATE = "2025-01-20"  # Date when pages were scraped


def build_base_metadata(row: Dict, extracted: Dict) -> Dict[str, Any]:
    """Build common metadata fields for all objects"""
    return {
        "page_id": row['page_id'],
        "object_id": row['object_id_suggested'] or f"{row['page_class']}-{row['page_id'][:8]}",
        "object_type": row['page_class'],
        "url": row['url'],
        "title": row['title'] or extracted['metadata'].get('title', ''),
        "classification_confidence": row.get('confidence', 'low'),
        "classification_notes": row.get('notes', ''),
        "source_html_path": row['html_file'],
        "last_scraped": SCRAPE_DATE,
        "last_processed": datetime.now().isoformat()
    }


def build_content_fields(extracted: Dict) -> Dict[str, Any]:
    """Build common content fields"""
    content = {
        "full_text": clean_whitespace(extracted['full_text']),
    }

    if extracted.get('sections'):
        content['sections'] = extracted['sections']

    # Create summary from first paragraph or section
    if extracted['sections']:
        first_section = extracted['sections'][0]
        summary = first_section.get('content', '')[:500]
        if summary:
            content['summary'] = clean_whitespace(summary) + "..."

    return content


def extract_related_pages(extracted: Dict, all_page_urls: Dict[str, str]) -> List[str]:
    """
    Extract related page object_ids from links in the HTML
    all_page_urls: dict mapping URL -> object_id
    """
    related = []
    for link in extracted.get('links', []):
        url = link['url']
        # Normalize URL
        url = url.rstrip('/')
        if url in all_page_urls:
            related_id = all_page_urls[url]
            if related_id not in related:
                related.append(related_id)

    return related


def build_degree_program_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for degree_program type"""
    program_info = extracted.get('program_info', {})

    # Try to extract program name from title
    title = row['title']
    program_name = re.sub(r'\s*\([^)]*\)', '', title).strip()  # Remove (Bachelor/Master)

    return {
        "metadata": build_base_metadata(row, extracted),
        "program_info": {
            "name": program_name,
            "degree_type": program_info.get('degree_type', ''),
            "degree_abbreviation": program_info.get('degree_abbreviation', ''),
            "duration_semesters": program_info.get('duration_semesters'),
            "ects_credits": program_info.get('ects_credits'),
            "language": program_info.get('language', ''),
            "start_semesters": program_info.get('start_semesters', []),
        },
        "admission_requirements": {},  # Will be populated by manual review or advanced extraction
        "curriculum": {
            "description": "",
            "related_curriculum_pages": [r for r in related if 'curriculum' in r]
        },
        "application_info": {
            "related_application_pages": [r for r in related if 'application' in r]
        },
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_curriculum_page_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for curriculum_page type"""
    # Extract module information from lists
    modules = []
    for lst in extracted.get('lists', []):
        for item in lst['items']:
            # Simple heuristic: if item contains "ECTS" or credit info, it's likely a module
            modules.append({
                "description": item,
                "credits": None  # Could extract with regex
            })

    return {
        "metadata": build_base_metadata(row, extracted),
        "curriculum_info": {
            "program_reference": [r for r in related if 'degree_program' in r],
            "module_type": "elective" if "elective" in row['title'].lower() else "core"
        },
        "modules": modules,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_application_process_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for application_process type"""
    # Try to extract steps from numbered lists or headings
    steps = []
    for i, section in enumerate(extracted.get('sections', []), 1):
        heading = section.get('heading', '')
        # Check if this looks like a step (e.g., "Step 1", "1.", numbered heading)
        if re.match(r'^\d+\.?\s', heading) or re.search(r'step\s+\d+', heading, re.I):
            steps.append({
                "step_number": i,
                "title": heading,
                "description": section.get('content', ''),
                "required": True
            })

    # If no explicit steps found, create from main sections
    if not steps:
        for i, section in enumerate(extracted.get('sections', [])[:10], 1):  # Limit to 10
            steps.append({
                "step_number": i,
                "title": section.get('heading', ''),
                "description": section.get('content', '')
            })

    # Try to extract deadlines
    full_text = extracted['full_text']
    deadlines = {}
    if 'july 15' in full_text.lower():
        deadlines['winter_semester'] = 'July 15'
    if 'january 15' in full_text.lower():
        deadlines['summer_semester'] = 'January 15'

    # Extract contact info
    contact = {}
    email = extract_email(full_text)
    if email:
        contact['email'] = email

    return {
        "metadata": build_base_metadata(row, extracted),
        "process_info": {
            "name": row['title'],
            "applies_to": [],  # Manual extraction needed
            "description": row['notes']
        },
        "steps": steps,
        "deadlines": deadlines if deadlines else None,
        "requirements": None,
        "fees": None,
        "contact": contact if contact else None,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_application_route_rule_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for application_route_rule type"""
    return {
        "metadata": build_base_metadata(row, extracted),
        "rule_info": {
            "rule_type": row['object_id_suggested'].split('-', 1)[1] if '-' in row['object_id_suggested'] else "general",
            "scope": "External requirement" if "visa" in row['title'].lower() else "Internal requirement",
            "applies_to": [],  # Extract from notes or content
            "description": row['notes']
        },
        "requirements": {},  # Extract from lists/tables
        "exceptions": [],
        "documentation": [],
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_language_proof_rule_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for language_proof_rule type"""
    title_lower = row['title'].lower()

    # Determine language
    language = None
    if 'german' in title_lower or 'dsh' in title_lower:
        language = "German"
    elif 'english' in title_lower:
        language = "English"

    return {
        "metadata": build_base_metadata(row, extracted),
        "language_info": {
            "language": language,
            "test_name": row['title'],
            "required_for": [],
            "description": row['notes']
        },
        "requirement_details": {},
        "test_details": None,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_fees_funding_rule_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for fees_funding_rule type"""
    # Try to extract amounts from text
    full_text = extracted['full_text']
    amounts = re.findall(r'€\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', full_text)

    return {
        "metadata": build_base_metadata(row, extracted),
        "financial_info": {
            "type": "funding" if "funding" in row['title'].lower() or "scholarship" in row['title'].lower() else "fee",
            "description": row['notes'],
            "amounts_mentioned": amounts
        },
        "eligibility": None,
        "application_process": None,
        "deadlines": None,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_deadline_rule_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for deadline_rule type"""
    # Extract dates from content
    full_text = extracted['full_text']
    dates_mentioned = []

    # Look for date patterns
    for match in re.finditer(r'\d{1,2}\.\d{1,2}\.(?:\d{4})?', full_text):
        dates_mentioned.append(match.group(0))

    return {
        "metadata": build_base_metadata(row, extracted),
        "deadline_info": {
            "type": "application_period" if "application" in row['title'].lower() else "academic_calendar",
            "applies_to": [],
            "description": row['notes']
        },
        "dates": {
            "dates_mentioned": dates_mentioned
        },
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_overview_navigation_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for overview_navigation type"""
    # Extract child pages from links
    child_pages = related  # All related pages are likely children

    return {
        "metadata": build_base_metadata(row, extracted),
        "navigation_info": {
            "purpose": row['notes'],
            "scope": row['title'],
            "audience": []
        },
        "sections": extracted.get('sections', []),
        "child_pages": child_pages,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_special_category_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for special_category type"""
    return {
        "metadata": build_base_metadata(row, extracted),
        "category_info": {
            "category_type": row['object_id_suggested'].split('-', 1)[1] if '-' in row['object_id_suggested'] else "general",
            "purpose": row['notes'],
            "audience": [],
            "time_bound": "ukraine" in row['title'].lower() or "crisis" in row['title'].lower()
        },
        "details": {},
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_accessibility_support_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for accessibility_support type"""
    return {
        "metadata": build_base_metadata(row, extracted),
        "support_info": {
            "service_type": row['title'],
            "who_for": [],
            "scope": row['notes']
        },
        "services": [],
        "contact": None,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_faq_support_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for faq_support type"""
    # Try to extract Q&A pairs from sections or lists
    questions = []
    for section in extracted.get('sections', []):
        heading = section.get('heading', '')
        content = section.get('content', '')
        if heading and content:
            questions.append({
                "question": heading,
                "answer": content
            })

    return {
        "metadata": build_base_metadata(row, extracted),
        "faq_info": {
            "topic": row['title'],
            "audience": [],
            "description": row['notes']
        },
        "questions": questions,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_university_profile_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for university_profile type"""
    return {
        "metadata": build_base_metadata(row, extracted),
        "profile_info": {
            "department": row['title'],
            "role": "",
            "offerings": row['notes']
        },
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


def build_family_support_object(row: Dict, extracted: Dict, related: List[str]) -> Dict:
    """Build object for family_support type"""
    return {
        "metadata": build_base_metadata(row, extracted),
        "support_info": {
            "service_type": row['title'],
            "who_for": ["students with children"],
            "description": row['notes']
        },
        "services": [],
        "contact": None,
        "related_pages": related,
        "content": build_content_fields(extracted)
    }


# Object builder registry
OBJECT_BUILDERS = {
    'degree_program': build_degree_program_object,
    'curriculum_page': build_curriculum_page_object,
    'application_process': build_application_process_object,
    'application_route_rule': build_application_route_rule_object,
    'language_proof_rule': build_language_proof_rule_object,
    'fees_funding_rule': build_fees_funding_rule_object,
    'deadline_rule': build_deadline_rule_object,
    'overview_navigation': build_overview_navigation_object,
    'special_category': build_special_category_object,
    'accessibility_support': build_accessibility_support_object,
    'faq_support': build_faq_support_object,
    'university_profile': build_university_profile_object,
    'family_support': build_family_support_object,
}


def main():
    """Main object building pipeline"""
    print("=" * 60)
    print("HTW SCRAPE - OBJECT BUILDER")
    print("=" * 60)
    print()

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Read CSV
    print(f"Reading classifications from {CSV_FILE}...")
    rows = []
    with CSV_FILE.open('r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip empty rows
            if not row.get('page_id') or not row.get('page_class'):
                continue
            rows.append(row)

    print(f"Found {len(rows)} classified pages")
    print()

    # Build URL -> object_id mapping for related pages
    url_to_object_id = {}
    for row in rows:
        url = row['url'].rstrip('/')
        object_id = row['object_id_suggested'] or f"{row['page_class']}-{row['page_id'][:8]}"
        url_to_object_id[url] = object_id

    # Process each page
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'by_type': {}
    }

    for row in rows:
        page_id = row['page_id']
        page_class = row['page_class']
        title = row['title']

        print(f"Processing: {title[:50]}... ({page_class})")

        try:
            # Load and extract HTML
            html_path = SNAPSHOTS_DIR / f"{page_id}.html"
            if not html_path.exists():
                print(f"  WARNING: HTML file not found: {html_path}")
                stats['failed'] += 1
                continue

            extracted = extract_all(str(html_path))

            # Extract related pages
            related = extract_related_pages(extracted, url_to_object_id)

            # Build object using type-specific builder
            builder = OBJECT_BUILDERS.get(page_class)
            if not builder:
                print(f"  WARNING: No builder for type '{page_class}'")
                stats['failed'] += 1
                continue

            obj = builder(row, extracted, related)

            # Save to JSON file
            object_id = obj['metadata']['object_id']
            output_file = OUTPUT_DIR / f"{object_id}.json"

            with output_file.open('w', encoding='utf-8') as f:
                json.dump(obj, f, indent=2, ensure_ascii=False)

            print(f"  ✓ Saved to {output_file.name}")
            stats['success'] += 1
            stats['by_type'][page_class] = stats['by_type'].get(page_class, 0) + 1

        except Exception as e:
            print(f"  ERROR: {e}")
            stats['failed'] += 1

        stats['total'] += 1

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total processed: {stats['total']}")
    print(f"Successful:      {stats['success']}")
    print(f"Failed:          {stats['failed']}")
    print()
    print("Objects by type:")
    for obj_type in sorted(stats['by_type'].keys()):
        count = stats['by_type'][obj_type]
        print(f"  {obj_type:30s} {count:3d}")
    print()
    print(f"Objects saved to: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
