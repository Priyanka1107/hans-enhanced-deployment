#!/usr/bin/env python3
"""
Generate detailed examples report for enrichment opportunities
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List

def load_json_file(filepath: str) -> Dict:
    """Load a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {}

def analyze_specific_object(obj: Dict, obj_type: str) -> Dict:
    """Analyze a specific object in detail."""
    report = {
        'id': obj['metadata']['object_id'],
        'type': obj_type,
        'url': obj['metadata']['url'],
        'title': obj['metadata']['title'],
        'confidence': obj['metadata']['classification_confidence'],
        'issues': [],
        'opportunities': [],
        'text_length': len(obj.get('content', {}).get('full_text', ''))
    }

    full_text = obj.get('content', {}).get('full_text', '')

    # Type-specific analysis
    if obj_type == 'degree_program':
        # Check duration
        if not obj.get('program_info', {}).get('duration_semesters'):
            duration_match = re.search(r'(\d+)\s*semesters?', full_text, re.IGNORECASE)
            if duration_match:
                report['opportunities'].append({
                    'field': 'duration_semesters',
                    'value_in_text': duration_match.group(1),
                    'current_value': None
                })

        # Check ECTS
        if not obj.get('program_info', {}).get('ects_credits'):
            ects_match = re.search(r'(\d+)\s*ECTS', full_text, re.IGNORECASE)
            if ects_match:
                report['opportunities'].append({
                    'field': 'ects_credits',
                    'value_in_text': ects_match.group(1),
                    'current_value': obj.get('program_info', {}).get('ects_credits')
                })

        # Check language
        if not obj.get('program_info', {}).get('language'):
            if 'english' in full_text.lower() or 'taught in english' in full_text.lower():
                report['opportunities'].append({
                    'field': 'language',
                    'value_in_text': 'English (detected)',
                    'current_value': obj.get('program_info', {}).get('language')
                })

    elif obj_type == 'fees_funding_rule':
        amounts = obj.get('financial_info', {}).get('amounts_mentioned', [])

        # Find all amounts in text
        amount_patterns = re.findall(r'(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?)\s*(?:€|EUR|euros?)', full_text, re.IGNORECASE)

        if amount_patterns and not amounts:
            report['opportunities'].append({
                'field': 'amounts_mentioned',
                'value_in_text': amount_patterns[:5],
                'current_value': amounts,
                'count': len(amount_patterns)
            })

        # Check for eligibility criteria
        if not obj.get('eligibility'):
            eligibility_keywords = ['eligible', 'qualification', 'requirement', 'must be', 'should be']
            if any(kw in full_text.lower() for kw in eligibility_keywords):
                report['opportunities'].append({
                    'field': 'eligibility',
                    'value_in_text': 'Eligibility criteria present in text',
                    'current_value': None
                })

        # Check for deadlines
        if not obj.get('deadlines'):
            deadline_matches = re.findall(r'deadline[s]?:?\s*([^.]+)', full_text, re.IGNORECASE)
            if deadline_matches:
                report['opportunities'].append({
                    'field': 'deadlines',
                    'value_in_text': deadline_matches[:3],
                    'current_value': None
                })

    elif obj_type == 'application_process':
        steps = obj.get('steps', [])

        # Find step-like patterns
        step_patterns = [
            r'Step \d+:?\s*([^.]+)',
            r'Phase \d+:?\s*([^.]+)',
            r'\d+\.\s+([^.]+)',
            r'First[,\s]+([^.]+).*?(?:Second|Then|Next)',
        ]

        extracted_steps = []
        for pattern in step_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            extracted_steps.extend(matches)

        if extracted_steps and not steps:
            report['opportunities'].append({
                'field': 'steps',
                'value_in_text': extracted_steps[:5],
                'current_value': steps,
                'count': len(extracted_steps)
            })

        # Check for deadlines
        if not obj.get('deadlines'):
            date_patterns = re.findall(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', full_text)
            if date_patterns:
                report['opportunities'].append({
                    'field': 'deadlines',
                    'value_in_text': date_patterns[:5],
                    'current_value': None,
                    'count': len(date_patterns)
                })

        # Check for requirements
        if not obj.get('requirements'):
            req_keywords = ['required', 'must', 'necessary', 'prerequisite']
            if any(kw in full_text.lower() for kw in req_keywords):
                report['opportunities'].append({
                    'field': 'requirements',
                    'value_in_text': 'Requirements present in text',
                    'current_value': None
                })

        # Check for contact info
        if not obj.get('contact'):
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', full_text)
            if emails:
                report['opportunities'].append({
                    'field': 'contact',
                    'value_in_text': emails[:3],
                    'current_value': None
                })

    elif obj_type == 'language_proof_rule':
        # Check test details
        if not obj.get('test_details'):
            test_keywords = ['score', 'level', 'grade', 'points', 'examination']
            if any(kw in full_text.lower() for kw in test_keywords):
                report['opportunities'].append({
                    'field': 'test_details',
                    'value_in_text': 'Test details present in text',
                    'current_value': None
                })

        # Check requirements
        if not obj.get('requirement_details') or obj.get('requirement_details') == {}:
            req_keywords = ['required', 'minimum', 'level', 'B1', 'B2', 'C1', 'C2']
            if any(kw in full_text for kw in req_keywords):
                report['opportunities'].append({
                    'field': 'requirement_details',
                    'value_in_text': 'Requirement details present in text',
                    'current_value': obj.get('requirement_details')
                })

    return report

def main():
    """Generate detailed examples report."""
    objects_dir = Path('/Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy/scapy/htw_scrape/outputs/objects/')

    # Priority object types to analyze
    priority_types = [
        'degree_program',
        'fees_funding_rule',
        'application_process',
        'language_proof_rule',
        'application_route_rule'
    ]

    print("=" * 100)
    print("DETAILED ENRICHMENT OPPORTUNITIES REPORT")
    print("=" * 100)

    for obj_type in priority_types:
        print(f"\n{'=' * 100}")
        print(f"OBJECT TYPE: {obj_type.upper()}")
        print(f"{'=' * 100}")

        # Find all objects of this type
        pattern = f"{obj_type}-*.json"
        files = list(objects_dir.glob(pattern))

        if not files:
            print(f"No objects found for type: {obj_type}")
            continue

        # Analyze first 5 objects
        analyzed = 0
        enrichment_candidates = []

        for file in files[:10]:  # Check up to 10
            obj = load_json_file(str(file))
            if not obj or 'metadata' not in obj:
                continue

            report = analyze_specific_object(obj, obj_type)

            if report['opportunities']:
                enrichment_candidates.append(report)
                analyzed += 1

            if analyzed >= 3:  # Show top 3 examples
                break

        # Print examples
        if enrichment_candidates:
            for i, candidate in enumerate(enrichment_candidates, 1):
                print(f"\n{'-' * 100}")
                print(f"EXAMPLE {i}: {candidate['title']}")
                print(f"{'-' * 100}")
                print(f"Object ID:   {candidate['id']}")
                print(f"URL:         {candidate['url']}")
                print(f"Confidence:  {candidate['confidence']}")
                print(f"Text Length: {candidate['text_length']} characters")
                print(f"\nEnrichment Opportunities ({len(candidate['opportunities'])} found):")

                for j, opp in enumerate(candidate['opportunities'], 1):
                    print(f"\n  {j}. Field: {opp['field']}")
                    print(f"     Current Value: {opp.get('current_value', 'None')}")

                    value_in_text = opp.get('value_in_text', '')
                    if isinstance(value_in_text, list):
                        print(f"     Found in Text: {value_in_text[:3]}")
                        if opp.get('count'):
                            print(f"     Total Found: {opp['count']}")
                    else:
                        print(f"     Found in Text: {value_in_text}")
        else:
            print(f"\nNo enrichment opportunities detected in sampled objects.")

    # Generate summary statistics
    print(f"\n{'=' * 100}")
    print("ENRICHMENT IMPACT ASSESSMENT")
    print(f"{'=' * 100}")

    impact_areas = [
        {
            'area': 'Degree Programs - Core Information',
            'fields': ['duration_semesters', 'ects_credits', 'language'],
            'priority': 'HIGH',
            'reason': 'Essential program details for student decision-making'
        },
        {
            'area': 'Application Process - Step-by-Step Guidance',
            'fields': ['steps', 'deadlines', 'requirements'],
            'priority': 'CRITICAL',
            'reason': 'Directly impacts user ability to complete applications'
        },
        {
            'area': 'Fees/Funding - Financial Planning',
            'fields': ['amounts_mentioned', 'eligibility', 'deadlines'],
            'priority': 'HIGH',
            'reason': 'Critical for financial planning and funding decisions'
        },
        {
            'area': 'Language Requirements - Test Details',
            'fields': ['test_details', 'requirement_details', 'required_for'],
            'priority': 'MEDIUM',
            'reason': 'Important for admission qualification verification'
        }
    ]

    for area in impact_areas:
        print(f"\n{area['area']}")
        print(f"  Priority: {area['priority']}")
        print(f"  Fields: {', '.join(area['fields'])}")
        print(f"  Reason: {area['reason']}")

    # Extraction method recommendations
    print(f"\n{'=' * 100}")
    print("RECOMMENDED EXTRACTION METHODS")
    print(f"{'=' * 100}")

    methods = [
        {
            'field_type': 'Numerical Values (ECTS, Duration, Amounts)',
            'method': 'Regex-based extraction with validation',
            'pattern_examples': [
                r'(\d+)\s*ECTS',
                r'(\d+)\s*semesters?',
                r'(\d{1,3}(?:[,\.]\d{3})*(?:[,\.]\d{2})?)\s*€'
            ]
        },
        {
            'field_type': 'Process Steps',
            'method': 'Pattern matching + NLP parsing',
            'pattern_examples': [
                r'Step \d+:?\s*([^.]+)',
                r'Phase \d+:?\s*([^.]+)',
                'Sequential markers: First, Second, Then, Next'
            ]
        },
        {
            'field_type': 'Dates and Deadlines',
            'method': 'Date parser with context analysis',
            'pattern_examples': [
                r'\d{1,2}[./]\d{1,2}[./]\d{2,4}',
                r'\d{2}\.\d{2}\.\d{4}',
                'Context keywords: deadline, until, by, before'
            ]
        },
        {
            'field_type': 'Eligibility Criteria',
            'method': 'Section extraction + list parsing',
            'pattern_examples': [
                'Section headers: Requirements, Eligibility, Prerequisites',
                'List items after requirement indicators',
                'Must/Should statements'
            ]
        }
    ]

    for method in methods:
        print(f"\n{method['field_type']}")
        print(f"  Method: {method['method']}")
        print(f"  Patterns:")
        for pattern in method['pattern_examples']:
            print(f"    - {pattern}")

    print(f"\n{'=' * 100}")
    print("END OF REPORT")
    print(f"{'=' * 100}")

if __name__ == "__main__":
    main()
