"""
Example Usage - How to Use the Generated Objects

This script demonstrates how to load and use the generated JSON objects
for a RAG/MCP student services Q&A system.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional


OBJECTS_DIR = Path("outputs/objects")


def load_object(object_id: str) -> Optional[Dict]:
    """Load a single object by its ID"""
    object_file = OBJECTS_DIR / f"{object_id}.json"
    if not object_file.exists():
        return None

    with object_file.open('r', encoding='utf-8') as f:
        return json.load(f)


def load_all_objects() -> List[Dict]:
    """Load all objects into memory"""
    objects = []
    for object_file in OBJECTS_DIR.glob("*.json"):
        with object_file.open('r', encoding='utf-8') as f:
            objects.append(json.load(f))
    return objects


def get_objects_by_type(object_type: str) -> List[Dict]:
    """Get all objects of a specific type"""
    all_objects = load_all_objects()
    return [obj for obj in all_objects if obj['metadata']['object_type'] == object_type]


def get_all_degree_programs() -> List[Dict]:
    """Get all degree programs"""
    return get_objects_by_type('degree_program')


def search_objects(query: str, limit: int = 5) -> List[Dict]:
    """
    Simple keyword search across all objects
    (In production, use vector embeddings for semantic search)
    """
    query_lower = query.lower()
    results = []

    for obj_file in OBJECTS_DIR.glob("*.json"):
        with obj_file.open('r', encoding='utf-8') as f:
            obj = json.load(f)

        # Search in title, notes, and full text
        searchable_text = " ".join([
            obj['metadata'].get('title', ''),
            obj['metadata'].get('classification_notes', ''),
            obj['content'].get('full_text', '')
        ]).lower()

        if query_lower in searchable_text:
            results.append(obj)

    return results[:limit]


def get_related_objects(object_id: str) -> List[Dict]:
    """Get all objects related to a given object"""
    obj = load_object(object_id)
    if not obj:
        return []

    related_ids = obj.get('related_pages', [])
    related_objects = []

    for related_id in related_ids:
        related_obj = load_object(related_id)
        if related_obj:
            related_objects.append(related_obj)

    return related_objects


def format_answer(obj: Dict, field_path: str = None) -> str:
    """
    Format an object as a human-readable answer
    """
    metadata = obj['metadata']
    answer = f"**{metadata['title']}**\n\n"

    if metadata.get('classification_notes'):
        answer += f"{metadata['classification_notes']}\n\n"

    # Add type-specific information
    obj_type = metadata['object_type']

    if obj_type == 'degree_program':
        program_info = obj.get('program_info', {})
        answer += "**Program Details:**\n"
        if program_info.get('degree_type'):
            answer += f"- Degree: {program_info.get('degree_type')} ({program_info.get('degree_abbreviation', '')})\n"
        if program_info.get('duration_semesters'):
            answer += f"- Duration: {program_info['duration_semesters']} semesters\n"
        if program_info.get('ects_credits'):
            answer += f"- ECTS: {program_info['ects_credits']} credits\n"
        if program_info.get('language'):
            answer += f"- Language: {program_info['language']}\n"
        if program_info.get('start_semesters'):
            answer += f"- Start: {', '.join(program_info['start_semesters'])} semester\n"

    elif obj_type == 'application_process':
        steps = obj.get('steps', [])
        if steps:
            answer += "**Application Steps:**\n"
            for step in steps:
                answer += f"{step.get('step_number', '')}. {step.get('title', '')}\n"

    elif obj_type == 'language_proof_rule':
        lang_info = obj.get('language_info', {})
        answer += "**Language Requirement:**\n"
        answer += f"- Language: {lang_info.get('language', '')}\n"
        answer += f"- Test: {lang_info.get('test_name', '')}\n"

    elif obj_type == 'fees_funding_rule':
        fin_info = obj.get('financial_info', {})
        answer += "**Financial Information:**\n"
        answer += f"- Type: {fin_info.get('type', '')}\n"

    # Add source URL
    answer += f"\n**Source:** {metadata['url']}\n"

    return answer


# ============================================================================
# Example Use Cases
# ============================================================================

def example_1_find_degree_programs():
    """Example 1: List all degree programs"""
    print("=" * 60)
    print("EXAMPLE 1: List All Degree Programs")
    print("=" * 60)

    programs = get_all_degree_programs()
    print(f"Found {len(programs)} degree programs:\n")

    for prog in programs:
        title = prog['metadata']['title']
        prog_type = prog['program_info'].get('degree_type', 'Unknown')
        print(f"  - {title} ({prog_type})")

    print()


def example_2_search_visa_info():
    """Example 2: Search for visa information"""
    print("=" * 60)
    print("EXAMPLE 2: Search for Visa Information")
    print("=" * 60)

    results = search_objects("visa", limit=3)
    print(f"Found {len(results)} results for 'visa':\n")

    for result in results:
        print(f"  - {result['metadata']['title']}")
        print(f"    Type: {result['metadata']['object_type']}")
        print(f"    URL: {result['metadata']['url']}")
        print()


def example_3_program_with_curriculum():
    """Example 3: Get program info with related curriculum"""
    print("=" * 60)
    print("EXAMPLE 3: Get IT Master's Program with Curriculum")
    print("=" * 60)

    # Load the IT Master's program (using one of the object IDs from CSV)
    programs = get_all_degree_programs()
    it_master = None
    for prog in programs:
        if "information technology" in prog['metadata']['title'].lower() and "master" in prog['metadata']['title'].lower():
            it_master = prog
            break

    if it_master:
        print(format_answer(it_master))

        # Get related curriculum pages
        related = get_related_objects(it_master['metadata']['object_id'])
        if related:
            print("**Related Pages:**")
            for rel in related:
                if rel['metadata']['object_type'] == 'curriculum_page':
                    print(f"  - {rel['metadata']['title']} ({rel['metadata']['url']})")
    else:
        print("IT Master's program not found")

    print()


def example_4_answer_student_question():
    """Example 4: Answer a student question using objects"""
    print("=" * 60)
    print("EXAMPLE 4: Answer Student Question")
    print("=" * 60)

    question = "What are the application deadlines?"
    print(f"Question: {question}\n")

    # Search for deadline-related objects
    results = search_objects("deadline application", limit=2)

    print("Answer based on found objects:\n")
    for result in results:
        print(format_answer(result))
        print()


def example_5_get_faq():
    """Example 5: Get FAQ content"""
    print("=" * 60)
    print("EXAMPLE 5: Get FAQ Content")
    print("=" * 60)

    faqs = get_objects_by_type('faq_support')
    print(f"Found {len(faqs)} FAQ pages:\n")

    for faq in faqs:
        print(f"**{faq['metadata']['title']}**")
        questions = faq.get('questions', [])
        if questions:
            print(f"  Contains {len(questions)} Q&A pairs")
            # Show first question
            if questions:
                first_q = questions[0]
                print(f"  Example: {first_q.get('question', '')[:50]}...")
        print()


# ============================================================================
# Main
# ============================================================================

def main():
    """Run all examples"""
    example_1_find_degree_programs()
    example_2_search_visa_info()
    example_3_program_with_curriculum()
    example_4_answer_student_question()
    example_5_get_faq()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total objects: {len(list(OBJECTS_DIR.glob('*.json')))}")
    print()
    print("Object types:")
    all_objects = load_all_objects()
    type_counts = {}
    for obj in all_objects:
        obj_type = obj['metadata']['object_type']
        type_counts[obj_type] = type_counts.get(obj_type, 0) + 1

    for obj_type in sorted(type_counts.keys()):
        print(f"  {obj_type:30s} {type_counts[obj_type]:3d}")
    print()


if __name__ == "__main__":
    main()
