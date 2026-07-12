#!/usr/bin/env python3
"""
Categorize HTW Berlin Student Services Q&A training data.
This script analyzes Q&A pairs and assigns semantic category tags.
"""

import pandas as pd
import re
from typing import List, Set
import json

# Define category patterns and keywords
CATEGORY_PATTERNS = {
    'application-process': [
        r'\b(apply|application|admission|deadline|submit|eligibility|requirement|document|transcript|certificate)\b',
        r'\b(how to apply|application process|apply for|admission requirement)\b',
        r'\b(when.*apply|application.*deadline|submission)\b'
    ],
    'language-requirements': [
        r'\b(english|german|language|ielts|toefl|dsh|testdaf|cambridge|b1|b2|c1|medium of instruction|moi)\b',
        r'\b(language.*requirement|proficiency|english.*test|german.*level)\b',
        r'\b(duolingo|pte|language certificate)\b'
    ],
    'program-info': [
        r'\b(program|course|study|bachelor|master|module|curriculum|semester)\b',
        r'\b(what.*study|program.*about|course.*content)\b',
        r'\b(duration|credits|ects)\b'
    ],
    'visa-immigration': [
        r'\b(visa|vpd|vorprüfungsdokumentation|residence|permit|immigration)\b',
        r'\b(student visa|residence permit|blocked account)\b',
        r'\b(embassy|consulate)\b'
    ],
    'fees-costs': [
        r'\b(fee|cost|tuition|payment|semester contribution|pay|expense)\b',
        r'\b(how much|price|free|charge)\b',
        r'\b(€|euro|money)\b'
    ],
    'transfer-credit': [
        r'\b(transfer|credit|recognition|previous|change|switch)\b',
        r'\b(university.*transfer|recognize.*credit|change.*program)\b',
        r'\b(anrechnung|anerkennung)\b'
    ],
    'application-portal': [
        r'\b(uni-assist|uniassist|portal|website|online|hochschulstart)\b',
        r'\b(where.*apply|application.*portal|submit.*online)\b',
        r'\b(login|account|register)\b'
    ]
}

# Program-specific patterns
PROGRAM_PATTERNS = {
    'international-business': [
        r'\b(international business|ib program|international.*management)\b',
        r'\b(business.*international|global.*business)\b'
    ],
    'cyber-security': [
        r'\b(cyber security|cybersecurity|information.*security|it security)\b',
        r'\b(security.*business|cyber.*program)\b'
    ],
    'construction-real-estate': [
        r'\b(construction|real estate|conrem|property|building)\b',
        r'\b(construction.*management|real.*estate.*management)\b'
    ],
    'game-design': [
        r'\b(game design|gaming|video game|game.*development)\b',
        r'\b(game.*program|design.*game)\b'
    ],
    'computer-science': [
        r'\b(computer science|informatics|software|programming|it program)\b',
        r'\b(cs program|information.*technology)\b'
    ]
}

def categorize_qa_pair(question: str, answer: str) -> Set[str]:
    """
    Categorize a Q&A pair based on content patterns.
    Returns a set of category tags.
    """
    tags = set()
    
    # Combine question and answer for analysis
    text = f"{question} {answer}".lower()
    
    # Check main categories
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                tags.add(category)
                break
    
    # Check program-specific categories
    for program, patterns in PROGRAM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                tags.add(program)
                break
    
    # Add sub-tags based on specific content
    if 'language-requirements' in tags:
        if re.search(r'\b(english|ielts|toefl|cambridge|duolingo|pte)\b', text, re.IGNORECASE):
            tags.add('english-proficiency')
        if re.search(r'\b(german|dsh|testdaf|b1|b2|c1)\b', text, re.IGNORECASE):
            tags.add('german-proficiency')
    
    if 'application-process' in tags:
        if re.search(r'\b(deadline|when.*apply|submission.*date)\b', text, re.IGNORECASE):
            tags.add('deadline')
        if re.search(r'\b(document|transcript|certificate|paper)\b', text, re.IGNORECASE):
            tags.add('documents')
        if re.search(r'\b(eligibility|requirement|qualify)\b', text, re.IGNORECASE):
            tags.add('eligibility')
    
    # If no categories found, mark as general
    if not tags:
        tags.add('general-inquiry')
    
    return tags

def process_excel_file(input_file: str, output_file: str):
    """
    Process the Excel file and add category tags.
    """
    print(f"Reading Excel file: {input_file}")
    
    # Read the Excel file
    df = pd.read_excel(input_file)
    
    # Ensure columns E and F exist (0-indexed: columns 4 and 5)
    if df.shape[1] < 6:
        raise ValueError("Excel file must have at least 6 columns (A-F)")
    
    # Get question and answer columns
    questions = df.iloc[:, 4]  # Column E
    answers = df.iloc[:, 5]     # Column F
    
    # Categorize each Q&A pair
    all_tags = []
    category_counts = {}
    
    for idx, (q, a) in enumerate(zip(questions, answers)):
        # Skip empty rows
        if pd.isna(q) or pd.isna(a):
            all_tags.append("")
            continue
        
        # Get tags for this pair
        tags = categorize_qa_pair(str(q), str(a))
        tags_str = "; ".join(sorted(tags))
        all_tags.append(tags_str)
        
        # Count categories for statistics
        for tag in tags:
            category_counts[tag] = category_counts.get(tag, 0) + 1
        
        # Progress indicator
        if (idx + 1) % 100 == 0:
            print(f"Processed {idx + 1} rows...")
    
    # Add tags column to dataframe
    df['Tags'] = all_tags
    
    # Save the updated Excel file
    print(f"\nSaving categorized data to: {output_file}")
    df.to_excel(output_file, index=False)
    
    # Print statistics
    print("\n=== Category Distribution ===")
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{category}: {count} occurrences")
    
    # Save category mapping for reference
    category_mapping = {
        "main_categories": list(CATEGORY_PATTERNS.keys()),
        "program_categories": list(PROGRAM_PATTERNS.keys()),
        "statistics": category_counts
    }
    
    mapping_file = input_file.replace('.xlsx', '_category_mapping.json')
    with open(mapping_file, 'w') as f:
        json.dump(category_mapping, f, indent=2)
    print(f"\nCategory mapping saved to: {mapping_file}")

if __name__ == "__main__":
    input_file = "HANS - Training Email Data.xlsx"
    output_file = "HANS - Training Email Data - Categorized.xlsx"
    
    try:
        process_excel_file(input_file, output_file)
        print("\nCategorization complete!")
    except Exception as e:
        print(f"Error: {e}")