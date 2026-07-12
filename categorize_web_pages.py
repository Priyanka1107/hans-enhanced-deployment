#!/usr/bin/env python3
"""
Categorize HTW Berlin web pages based on content analysis.
Maps each .txt file to relevant topic clusters.
"""

import os
import json
import re
from typing import Dict, Set, List
from pathlib import Path

# Same category patterns as used for Excel data
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
    ],
    'international-students': [
        r'\b(international|foreign|overseas|exchange|erasmus)\b',
        r'\b(international.*student|study.*abroad|incoming)\b'
    ],
    'campus-life': [
        r'\b(campus|student.*life|housing|accommodation|dormitory|residence)\b',
        r'\b(sport|culture|activity|club|society)\b',
        r'\b(mensa|cafeteria|library)\b'
    ],
    'career-services': [
        r'\b(career|job|internship|placement|employment|work)\b',
        r'\b(career.*service|job.*opportunity|praktikum)\b',
        r'\b(alumni|graduate.*employment)\b'
    ],
    'research': [
        r'\b(research|phd|doctorate|doctoral|publication|project)\b',
        r'\b(research.*group|laboratory|institute)\b'
    ],
    'contact-info': [
        r'\b(contact|email|phone|address|office.*hour|consultation)\b',
        r'\b(student.*service|advising|counseling|support)\b'
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
    ],
    'engineering': [
        r'\b(engineering|mechanical|electrical|civil|automotive)\b',
        r'\b(engineer.*program|technical.*study)\b'
    ],
    'design': [
        r'\b(design|communication.*design|visual|graphic|fashion)\b',
        r'\b(design.*program|creative.*study)\b'
    ],
    'business': [
        r'\b(business|management|economics|finance|marketing)\b',
        r'\b(business.*administration|bwl|wirtschaft)\b'
    ]
}

def analyze_file_content(file_path: Path) -> Set[str]:
    """
    Analyze a text file and return relevant category tags.
    """
    tags = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().lower()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return tags
    
    # Analyze filename for hints
    filename = file_path.stem.lower()
    
    # Check main categories
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                tags.add(category)
                break
    
    # Check program-specific categories
    for program, patterns in PROGRAM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                tags.add(program)
                break
    
    # Additional filename-based tagging
    if 'international' in filename:
        tags.add('international-students')
    if 'career' in filename:
        tags.add('career-services')
    if 'research' in filename:
        tags.add('research')
    if 'campus' in filename:
        tags.add('campus-life')
    if any(prog in filename for prog in ['business', 'bwl', 'wirtschaft']):
        tags.add('business')
    if any(prog in filename for prog in ['engineering', 'ingenieur', 'technik']):
        tags.add('engineering')
    if 'design' in filename:
        tags.add('design')
    
    # If no tags found, tag as general
    if not tags:
        tags.add('general-info')
    
    return tags

def categorize_web_pages(pages_dir: str, output_file: str):
    """
    Process all .txt files in the pages directory and create category mapping.
    """
    pages_path = Path(pages_dir)
    
    if not pages_path.exists():
        raise ValueError(f"Directory not found: {pages_dir}")
    
    # Dictionary to store mappings
    file_mappings = {}
    category_counts = {}
    
    # Get all .txt files
    txt_files = list(pages_path.glob("*.txt"))
    print(f"Found {len(txt_files)} text files to analyze")
    
    # Analyze each file
    for idx, txt_file in enumerate(txt_files):
        # Get tags for this file
        tags = analyze_file_content(txt_file)
        
        # Store mapping
        file_mappings[txt_file.name] = list(sorted(tags))
        
        # Count categories
        for tag in tags:
            category_counts[tag] = category_counts.get(tag, 0) + 1
        
        # Progress indicator
        if (idx + 1) % 20 == 0:
            print(f"Processed {idx + 1}/{len(txt_files)} files...")
    
    # Create output structure
    output_data = {
        "total_files": len(txt_files),
        "category_statistics": category_counts,
        "file_mappings": file_mappings
    }
    
    # Save to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nMapping saved to: {output_file}")
    
    # Print statistics
    print("\n=== Category Distribution ===")
    for category, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"{category}: {count} files")
    
    # Print sample mappings
    print("\n=== Sample File Mappings ===")
    sample_files = list(file_mappings.items())[:5]
    for filename, tags in sample_files:
        print(f"{filename}: {', '.join(tags)}")

if __name__ == "__main__":
    pages_dir = "pages"
    output_file = "web_pages_category_mapping.json"
    
    try:
        categorize_web_pages(pages_dir, output_file)
        print("\nWeb page categorization complete!")
    except Exception as e:
        print(f"Error: {e}")