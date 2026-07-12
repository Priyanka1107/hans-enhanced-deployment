#!/usr/bin/env python3
"""
Comprehensive Assessment of Scapy Objects for Enrichment Analysis
"""

import json
import os
from collections import defaultdict, Counter
from pathlib import Path
import re
from typing import Dict, List, Any, Tuple

def load_json_file(filepath: str) -> Dict:
    """Load a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}

def is_field_empty(value) -> bool:
    """Check if a field is considered empty."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False

def calculate_fill_rate(obj: Dict, fields: List[str]) -> Tuple[int, int]:
    """Calculate fill rate for specific fields in an object."""
    filled = 0
    total = len(fields)

    for field_path in fields:
        parts = field_path.split('.')
        current = obj

        # Navigate nested fields
        try:
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part, None)
                else:
                    current = None
                    break

            if not is_field_empty(current):
                filled += 1
        except:
            pass

    return filled, total

def analyze_degree_programs(objects: List[Dict]) -> Dict:
    """Analyze degree program objects."""
    results = {
        'total': len(objects),
        'field_analysis': {},
        'examples': {'good': [], 'poor': []},
        'issues': []
    }

    key_fields = [
        'program_info.name',
        'program_info.degree_type',
        'program_info.duration_semesters',
        'program_info.ects_credits',
        'program_info.language',
        'program_info.start_semesters',
        'admission_requirements',
        'curriculum.related_curriculum_pages'
    ]

    fill_rates = []

    for obj in objects:
        filled, total = calculate_fill_rate(obj, key_fields)
        fill_rate = filled / total if total > 0 else 0
        fill_rates.append(fill_rate)

        # Track individual field fills
        for field in key_fields:
            if field not in results['field_analysis']:
                results['field_analysis'][field] = {'filled': 0, 'empty': 0}

            parts = field.split('.')
            current = obj
            try:
                for part in parts:
                    current = current.get(part, None) if isinstance(current, dict) else None

                if is_field_empty(current):
                    results['field_analysis'][field]['empty'] += 1
                else:
                    results['field_analysis'][field]['filled'] += 1
            except:
                results['field_analysis'][field]['empty'] += 1

        # Categorize examples
        if fill_rate >= 0.7:
            if len(results['examples']['good']) < 3:
                results['examples']['good'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate,
                    'url': obj['metadata']['url']
                })
        elif fill_rate < 0.4:
            if len(results['examples']['poor']) < 3:
                results['examples']['poor'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate,
                    'url': obj['metadata']['url'],
                    'missing_fields': [f for f in key_fields if is_field_empty(get_nested_field(obj, f))]
                })

    results['avg_fill_rate'] = sum(fill_rates) / len(fill_rates) if fill_rates else 0

    return results

def analyze_fees_funding(objects: List[Dict]) -> Dict:
    """Analyze fees and funding objects."""
    results = {
        'total': len(objects),
        'field_analysis': {},
        'examples': {'good': [], 'poor': []},
        'issues': []
    }

    key_fields = [
        'financial_info.type',
        'financial_info.description',
        'financial_info.amounts_mentioned',
        'eligibility',
        'application_process',
        'deadlines'
    ]

    fill_rates = []
    amount_parsing = {'has_amounts': 0, 'no_amounts': 0, 'amounts_in_text': 0}

    for obj in objects:
        filled, total = calculate_fill_rate(obj, key_fields)
        fill_rate = filled / total if total > 0 else 0
        fill_rates.append(fill_rate)

        # Check amounts parsing
        amounts = obj.get('financial_info', {}).get('amounts_mentioned', [])
        full_text = obj.get('content', {}).get('full_text', '')

        if amounts and len(amounts) > 0:
            amount_parsing['has_amounts'] += 1
        else:
            amount_parsing['no_amounts'] += 1
            # Check if amounts exist in text but weren't extracted
            if re.search(r'\d+(?:,\d+)?(?:\.\d+)?\s*€|€\s*\d+(?:,\d+)?(?:\.\d+)?', full_text):
                amount_parsing['amounts_in_text'] += 1

        # Track field fills
        for field in key_fields:
            if field not in results['field_analysis']:
                results['field_analysis'][field] = {'filled': 0, 'empty': 0}

            val = get_nested_field(obj, field)
            if is_field_empty(val):
                results['field_analysis'][field]['empty'] += 1
            else:
                results['field_analysis'][field]['filled'] += 1

        # Examples
        if fill_rate >= 0.7:
            if len(results['examples']['good']) < 3:
                results['examples']['good'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate,
                    'has_amounts': len(amounts) > 0
                })
        elif fill_rate < 0.4:
            if len(results['examples']['poor']) < 3:
                results['examples']['poor'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate,
                    'has_amounts': len(amounts) > 0
                })

    results['avg_fill_rate'] = sum(fill_rates) / len(fill_rates) if fill_rates else 0
    results['amount_parsing'] = amount_parsing

    return results

def analyze_application_process(objects: List[Dict]) -> Dict:
    """Analyze application process objects."""
    results = {
        'total': len(objects),
        'field_analysis': {},
        'examples': {'good': [], 'poor': []},
        'issues': []
    }

    key_fields = [
        'process_info.name',
        'process_info.applies_to',
        'steps',
        'deadlines',
        'requirements',
        'fees',
        'contact'
    ]

    fill_rates = []

    for obj in objects:
        filled, total = calculate_fill_rate(obj, key_fields)
        fill_rate = filled / total if total > 0 else 0
        fill_rates.append(fill_rate)

        # Track field fills
        for field in key_fields:
            if field not in results['field_analysis']:
                results['field_analysis'][field] = {'filled': 0, 'empty': 0}

            val = get_nested_field(obj, field)
            if is_field_empty(val):
                results['field_analysis'][field]['empty'] += 1
            else:
                results['field_analysis'][field]['filled'] += 1

        # Check if steps should be extracted from text
        steps = obj.get('steps', [])
        full_text = obj.get('content', {}).get('full_text', '')

        if len(steps) == 0 and ('step' in full_text.lower() or 'process' in full_text.lower()):
            results['issues'].append({
                'id': obj['metadata']['object_id'],
                'issue': 'Steps likely exist in text but not extracted',
                'text_length': len(full_text)
            })

        # Examples
        if fill_rate >= 0.6:
            if len(results['examples']['good']) < 3:
                results['examples']['good'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate,
                    'has_steps': len(steps) > 0
                })
        elif fill_rate < 0.3:
            if len(results['examples']['poor']) < 3:
                results['examples']['poor'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate,
                    'has_steps': len(steps) > 0
                })

    results['avg_fill_rate'] = sum(fill_rates) / len(fill_rates) if fill_rates else 0

    return results

def analyze_language_proof(objects: List[Dict]) -> Dict:
    """Analyze language proof rule objects."""
    results = {
        'total': len(objects),
        'field_analysis': {},
        'examples': {'good': [], 'poor': []},
        'issues': []
    }

    key_fields = [
        'language_info.language',
        'language_info.test_name',
        'language_info.required_for',
        'requirement_details',
        'test_details'
    ]

    fill_rates = []

    for obj in objects:
        filled, total = calculate_fill_rate(obj, key_fields)
        fill_rate = filled / total if total > 0 else 0
        fill_rates.append(fill_rate)

        # Track field fills
        for field in key_fields:
            if field not in results['field_analysis']:
                results['field_analysis'][field] = {'filled': 0, 'empty': 0}

            val = get_nested_field(obj, field)
            if is_field_empty(val):
                results['field_analysis'][field]['empty'] += 1
            else:
                results['field_analysis'][field]['filled'] += 1

        # Examples
        if fill_rate >= 0.6:
            if len(results['examples']['good']) < 3:
                results['examples']['good'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate
                })
        elif fill_rate < 0.4:
            if len(results['examples']['poor']) < 3:
                results['examples']['poor'].append({
                    'id': obj['metadata']['object_id'],
                    'fill_rate': fill_rate
                })

    results['avg_fill_rate'] = sum(fill_rates) / len(fill_rates) if fill_rates else 0

    return results

def get_nested_field(obj: Dict, field_path: str) -> Any:
    """Get a nested field value from an object."""
    parts = field_path.split('.')
    current = obj

    try:
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part, None)
            else:
                return None
        return current
    except:
        return None

def analyze_classification_quality(objects: List[Dict]) -> Dict:
    """Analyze classification quality across all objects."""
    confidence_counts = Counter()
    notes_quality = {'specific': 0, 'generic': 0, 'empty': 0}

    for obj in objects:
        confidence = obj.get('metadata', {}).get('classification_confidence', 'unknown')
        confidence_counts[confidence] += 1

        notes = obj.get('metadata', {}).get('classification_notes', '')

        if not notes or notes.strip() == '':
            notes_quality['empty'] += 1
        elif len(notes) > 50 and any(keyword in notes.lower() for keyword in ['explains', 'details', 'contains', 'provides', 'describes']):
            notes_quality['specific'] += 1
        else:
            notes_quality['generic'] += 1

    return {
        'confidence_distribution': dict(confidence_counts),
        'notes_quality': notes_quality,
        'total_objects': len(objects)
    }

def analyze_content_vs_structured_gap(objects: List[Dict]) -> Dict:
    """Analyze gap between full_text content and structured fields."""
    gaps = {
        'dates_in_text_not_structured': [],
        'amounts_in_text_not_structured': [],
        'lists_in_text_not_structured': [],
        'contacts_in_text_not_structured': []
    }

    for obj in objects:
        full_text = obj.get('content', {}).get('full_text', '')
        obj_id = obj['metadata']['object_id']
        obj_type = obj['metadata']['object_type']

        # Check for dates
        dates_in_text = re.findall(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}|\d{4}-\d{2}-\d{2}', full_text)
        if dates_in_text and obj_type in ['application_process', 'deadline_rule']:
            deadlines = obj.get('deadlines', None) or obj.get('dates', {}).get('dates_mentioned', [])
            if is_field_empty(deadlines) or (isinstance(deadlines, list) and len(deadlines) == 0):
                gaps['dates_in_text_not_structured'].append({
                    'id': obj_id,
                    'type': obj_type,
                    'dates_found': len(dates_in_text)
                })

        # Check for amounts
        amounts_in_text = re.findall(r'\d+(?:,\d+)?(?:\.\d+)?\s*(?:€|EUR|euros?)', full_text, re.IGNORECASE)
        if amounts_in_text and obj_type == 'fees_funding_rule':
            amounts_structured = obj.get('financial_info', {}).get('amounts_mentioned', [])
            if is_field_empty(amounts_structured):
                gaps['amounts_in_text_not_structured'].append({
                    'id': obj_id,
                    'amounts_found': len(amounts_in_text),
                    'examples': amounts_in_text[:3]
                })

        # Check for step-like structures
        if obj_type == 'application_process':
            step_indicators = len(re.findall(r'(?:step\s+\d+|stage\s+\d+|\d+\.|first|second|third|then|next)', full_text, re.IGNORECASE))
            steps_structured = obj.get('steps', [])
            if step_indicators >= 3 and len(steps_structured) == 0:
                gaps['lists_in_text_not_structured'].append({
                    'id': obj_id,
                    'step_indicators': step_indicators
                })

        # Check for contact info
        emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', full_text)
        if emails and obj_type == 'application_process':
            contact = obj.get('contact', None)
            if is_field_empty(contact):
                gaps['contacts_in_text_not_structured'].append({
                    'id': obj_id,
                    'emails_found': emails[:2]
                })

    return gaps

def main():
    """Main analysis function."""
    objects_dir = Path('/Users/koware/Desktop/HANS/Hans_DB/hans_experiments/baseline_copy/scapy/htw_scrape/outputs/objects/')

    # Load all objects
    all_objects = []
    objects_by_type = defaultdict(list)

    print("Loading objects...")
    for file in objects_dir.glob('*.json'):
        obj = load_json_file(str(file))
        if obj and 'metadata' in obj:
            all_objects.append(obj)
            obj_type = obj['metadata'].get('object_type', 'unknown')
            objects_by_type[obj_type].append(obj)

    print(f"\nLoaded {len(all_objects)} objects across {len(objects_by_type)} types\n")

    # Type distribution
    print("=" * 80)
    print("OBJECT TYPE DISTRIBUTION")
    print("=" * 80)
    for obj_type, objs in sorted(objects_by_type.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"  {obj_type:30} : {len(objs):3} objects")

    # Classification quality
    print("\n" + "=" * 80)
    print("CLASSIFICATION QUALITY ANALYSIS")
    print("=" * 80)
    classification_analysis = analyze_classification_quality(all_objects)
    print(f"\nConfidence Distribution:")
    for conf, count in sorted(classification_analysis['confidence_distribution'].items()):
        pct = (count / classification_analysis['total_objects']) * 100
        print(f"  {conf:10} : {count:3} objects ({pct:5.1f}%)")

    print(f"\nClassification Notes Quality:")
    for quality, count in classification_analysis['notes_quality'].items():
        pct = (count / classification_analysis['total_objects']) * 100
        print(f"  {quality:10} : {count:3} objects ({pct:5.1f}%)")

    # Degree programs analysis
    if 'degree_program' in objects_by_type:
        print("\n" + "=" * 80)
        print("DEGREE PROGRAM OBJECTS ANALYSIS")
        print("=" * 80)
        dp_analysis = analyze_degree_programs(objects_by_type['degree_program'])
        print(f"\nTotal degree programs: {dp_analysis['total']}")
        print(f"Average fill rate: {dp_analysis['avg_fill_rate']:.1%}")
        print(f"\nField-by-field analysis:")
        for field, stats in dp_analysis['field_analysis'].items():
            total = stats['filled'] + stats['empty']
            fill_pct = (stats['filled'] / total * 100) if total > 0 else 0
            print(f"  {field:40} : {stats['filled']:2}/{total:2} filled ({fill_pct:5.1f}%)")

        if dp_analysis['examples']['poor']:
            print(f"\nPoorly filled examples:")
            for ex in dp_analysis['examples']['poor']:
                print(f"  {ex['id']:40} - Fill rate: {ex['fill_rate']:.1%}")
                print(f"    Missing: {', '.join(ex.get('missing_fields', [])[:3])}")

    # Fees/Funding analysis
    if 'fees_funding_rule' in objects_by_type:
        print("\n" + "=" * 80)
        print("FEES/FUNDING OBJECTS ANALYSIS")
        print("=" * 80)
        ff_analysis = analyze_fees_funding(objects_by_type['fees_funding_rule'])
        print(f"\nTotal fees/funding objects: {ff_analysis['total']}")
        print(f"Average fill rate: {ff_analysis['avg_fill_rate']:.1%}")
        print(f"\nAmount parsing quality:")
        for metric, count in ff_analysis['amount_parsing'].items():
            print(f"  {metric:20} : {count}")

        print(f"\nField-by-field analysis:")
        for field, stats in ff_analysis['field_analysis'].items():
            total = stats['filled'] + stats['empty']
            fill_pct = (stats['filled'] / total * 100) if total > 0 else 0
            print(f"  {field:40} : {stats['filled']:2}/{total:2} filled ({fill_pct:5.1f}%)")

    # Application process analysis
    if 'application_process' in objects_by_type:
        print("\n" + "=" * 80)
        print("APPLICATION PROCESS OBJECTS ANALYSIS")
        print("=" * 80)
        ap_analysis = analyze_application_process(objects_by_type['application_process'])
        print(f"\nTotal application process objects: {ap_analysis['total']}")
        print(f"Average fill rate: {ap_analysis['avg_fill_rate']:.1%}")

        print(f"\nField-by-field analysis:")
        for field, stats in ap_analysis['field_analysis'].items():
            total = stats['filled'] + stats['empty']
            fill_pct = (stats['filled'] / total * 100) if total > 0 else 0
            print(f"  {field:40} : {stats['filled']:2}/{total:2} filled ({fill_pct:5.1f}%)")

        if ap_analysis['issues']:
            print(f"\nIssues detected ({len(ap_analysis['issues'])} objects):")
            for issue in ap_analysis['issues'][:5]:
                print(f"  {issue['id']:40} - {issue['issue']}")

    # Language proof analysis
    if 'language_proof_rule' in objects_by_type:
        print("\n" + "=" * 80)
        print("LANGUAGE PROOF RULE OBJECTS ANALYSIS")
        print("=" * 80)
        lp_analysis = analyze_language_proof(objects_by_type['language_proof_rule'])
        print(f"\nTotal language proof objects: {lp_analysis['total']}")
        print(f"Average fill rate: {lp_analysis['avg_fill_rate']:.1%}")

        print(f"\nField-by-field analysis:")
        for field, stats in lp_analysis['field_analysis'].items():
            total = stats['filled'] + stats['empty']
            fill_pct = (stats['filled'] / total * 100) if total > 0 else 0
            print(f"  {field:40} : {stats['filled']:2}/{total:2} filled ({fill_pct:5.1f}%)")

    # Content vs Structured gap analysis
    print("\n" + "=" * 80)
    print("CONTENT VS STRUCTURED FIELDS GAP ANALYSIS")
    print("=" * 80)
    gap_analysis = analyze_content_vs_structured_gap(all_objects)

    print(f"\nDates in text but not in structured fields:")
    print(f"  {len(gap_analysis['dates_in_text_not_structured'])} objects")
    for item in gap_analysis['dates_in_text_not_structured'][:3]:
        print(f"    {item['id']:40} ({item['type']}) - {item['dates_found']} dates found")

    print(f"\nAmounts in text but not in structured fields:")
    print(f"  {len(gap_analysis['amounts_in_text_not_structured'])} objects")
    for item in gap_analysis['amounts_in_text_not_structured'][:3]:
        print(f"    {item['id']:40} - {item['amounts_found']} amounts: {item['examples'][:2]}")

    print(f"\nProcess steps in text but not extracted:")
    print(f"  {len(gap_analysis['lists_in_text_not_structured'])} objects")
    for item in gap_analysis['lists_in_text_not_structured'][:3]:
        print(f"    {item['id']:40} - {item['step_indicators']} step indicators")

    print(f"\nContact info in text but not structured:")
    print(f"  {len(gap_analysis['contacts_in_text_not_structured'])} objects")
    for item in gap_analysis['contacts_in_text_not_structured'][:3]:
        print(f"    {item['id']:40} - Emails: {item['emails_found']}")

    # Summary and recommendations
    print("\n" + "=" * 80)
    print("ENRICHMENT RECOMMENDATIONS (PRIORITIZED)")
    print("=" * 80)

    recommendations = []

    # Calculate priorities
    if 'application_process' in objects_by_type:
        ap_fill = analyze_application_process(objects_by_type['application_process'])['avg_fill_rate']
        if ap_fill < 0.5:
            recommendations.append({
                'priority': 1,
                'type': 'application_process',
                'issue': f'Low fill rate ({ap_fill:.1%})',
                'action': 'Extract steps, deadlines, requirements, and contact info from full_text',
                'impact': 'HIGH - Critical for user journeys'
            })

    if gap_analysis['dates_in_text_not_structured']:
        recommendations.append({
            'priority': 1,
            'type': 'deadline_rule / application_process',
            'issue': f"{len(gap_analysis['dates_in_text_not_structured'])} objects with unstructured dates",
            'action': 'Improve date extraction and normalization',
            'impact': 'HIGH - Essential for deadlines'
        })

    if gap_analysis['amounts_in_text_not_structured']:
        recommendations.append({
            'priority': 2,
            'type': 'fees_funding_rule',
            'issue': f"{len(gap_analysis['amounts_in_text_not_structured'])} objects with unextracted amounts",
            'action': 'Enhance amount parsing from text',
            'impact': 'MEDIUM - Important for financial planning'
        })

    if 'degree_program' in objects_by_type:
        dp_fill = analyze_degree_programs(objects_by_type['degree_program'])['avg_fill_rate']
        if dp_fill < 0.6:
            recommendations.append({
                'priority': 2,
                'type': 'degree_program',
                'issue': f'Incomplete program info ({dp_fill:.1%} fill rate)',
                'action': 'Extract duration, ECTS, language, start semesters',
                'impact': 'MEDIUM - Core program information'
            })

    if gap_analysis['lists_in_text_not_structured']:
        recommendations.append({
            'priority': 2,
            'type': 'application_process',
            'issue': f"{len(gap_analysis['lists_in_text_not_structured'])} objects with unextracted steps",
            'action': 'Implement step/process extraction',
            'impact': 'MEDIUM - Helps structure guidance'
        })

    if gap_analysis['contacts_in_text_not_structured']:
        recommendations.append({
            'priority': 3,
            'type': 'application_process',
            'issue': f"{len(gap_analysis['contacts_in_text_not_structured'])} objects missing contact extraction",
            'action': 'Extract emails, phone numbers, office hours',
            'impact': 'LOW-MEDIUM - Useful for support'
        })

    # Print recommendations
    for i, rec in enumerate(sorted(recommendations, key=lambda x: x['priority']), 1):
        print(f"\n{i}. [{rec['impact']}] {rec['type']}")
        print(f"   Issue: {rec['issue']}")
        print(f"   Action: {rec['action']}")

    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
