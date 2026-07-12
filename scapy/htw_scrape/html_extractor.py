"""
HTML Content Extraction Utilities

This module provides functions to parse HTML files and extract structured content
for building objects. Uses BeautifulSoup for HTML parsing.
"""

from bs4 import BeautifulSoup
from pathlib import Path
from typing import Dict, List, Optional, Any
import re


def load_html(html_path: str) -> BeautifulSoup:
    """Load and parse an HTML file"""
    with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html_content = f.read()
    return BeautifulSoup(html_content, 'html.parser')


def extract_main_content(soup: BeautifulSoup) -> Optional[BeautifulSoup]:
    """
    Extract the main content area, removing navigation, headers, footers
    Priority order: <main>, id="main", class containing "content" or "main"
    """
    # Try <main> tag first
    main = soup.find('main')
    if main:
        return main

    # Try id="main" or similar
    main = soup.find(id=re.compile(r'main|content', re.I))
    if main:
        return main

    # Try class containing "main" or "content"
    main = soup.find(class_=re.compile(r'main|content', re.I))
    if main:
        return main

    # Fallback to body
    return soup.find('body')


def extract_text(soup: BeautifulSoup, clean: bool = True) -> str:
    """
    Extract all text from HTML, optionally cleaning whitespace
    """
    text = soup.get_text(separator=' ', strip=True)
    if clean:
        # Collapse multiple spaces/newlines
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
    return text


def extract_headings(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """
    Extract all headings (h1-h6) with their levels and text
    """
    headings = []
    for level in range(1, 7):
        for heading in soup.find_all(f'h{level}'):
            headings.append({
                'level': level,
                'text': heading.get_text(strip=True)
            })
    return headings


def extract_lists(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract all lists (ul, ol) with their items
    """
    lists = []
    for list_tag in soup.find_all(['ul', 'ol']):
        items = [li.get_text(strip=True) for li in list_tag.find_all('li', recursive=False)]
        if items:  # Only include non-empty lists
            lists.append({
                'type': list_tag.name,  # 'ul' or 'ol'
                'items': items
            })
    return lists


def extract_tables(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract all tables with headers and rows
    """
    tables = []
    for table in soup.find_all('table'):
        headers = []
        rows = []

        # Extract headers
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]

        # Extract rows
        tbody = table.find('tbody') or table
        for tr in tbody.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells:  # Only include non-empty rows
                rows.append(cells)

        if rows:  # Only include non-empty tables
            tables.append({
                'headers': headers,
                'rows': rows
            })

    return tables


def extract_links(soup: BeautifulSoup, base_url: str = "https://www.htw-berlin.de") -> List[Dict[str, str]]:
    """
    Extract all internal links with their text and URLs
    """
    links = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        text = link.get_text(strip=True)

        # Filter for internal HTW links
        if '/en/' in href or href.startswith('/'):
            if not href.startswith('http'):
                href = base_url + href

            if text:  # Only include links with text
                links.append({
                    'text': text,
                    'url': href
                })

    return links


def extract_sections(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """
    Extract content organized by sections (headings + following content)
    """
    sections = []
    main_content = extract_main_content(soup)
    if not main_content:
        return sections

    # Find all headings
    headings = main_content.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])

    for i, heading in enumerate(headings):
        # Get all siblings between this heading and the next
        content_elements = []
        next_heading = headings[i + 1] if i + 1 < len(headings) else None

        current = heading.find_next_sibling()
        while current and current != next_heading:
            if current.name in ['p', 'ul', 'ol', 'table', 'div']:
                content_elements.append(current)
            current = current.find_next_sibling()

        # Extract text from collected elements
        section_text = ' '.join([elem.get_text(strip=True) for elem in content_elements])

        if section_text:  # Only include sections with content
            sections.append({
                'heading': heading.get_text(strip=True),
                'level': int(heading.name[1]),  # Extract number from h1, h2, etc.
                'content': section_text
            })

    return sections


def extract_metadata(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract metadata from HTML head (title, meta tags)
    """
    metadata = {}

    # Title
    title = soup.find('title')
    if title:
        metadata['title'] = title.get_text(strip=True)

    # Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc and meta_desc.get('content'):
        metadata['description'] = meta_desc['content']

    # Meta keywords
    meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
    if meta_keywords and meta_keywords.get('content'):
        metadata['keywords'] = meta_keywords['content']

    return metadata


def extract_program_info(soup: BeautifulSoup) -> Dict[str, Any]:
    """
    Extract degree program-specific information using pattern matching
    This is a heuristic approach - may need refinement based on actual HTML structure
    """
    info = {}
    text = extract_text(soup).lower()

    # Degree type
    if 'master' in text:
        info['degree_type'] = 'Master'
        info['degree_abbreviation'] = 'M.Sc.' if 'science' in text else 'M.A.'
    elif 'bachelor' in text:
        info['degree_type'] = 'Bachelor'
        info['degree_abbreviation'] = 'B.Sc.' if 'science' in text else 'B.A.'

    # Duration (look for "X semesters" or "X semester")
    semester_match = re.search(r'(\d+)\s+semesters?', text)
    if semester_match:
        info['duration_semesters'] = int(semester_match.group(1))

    # ECTS credits
    ects_match = re.search(r'(\d+)\s+ects', text)
    if ects_match:
        info['ects_credits'] = int(ects_match.group(1))

    # Language
    if 'english' in text and ('taught in english' in text or 'language: english' in text):
        info['language'] = 'English'
    elif 'german' in text and ('taught in german' in text or 'language: german' in text):
        info['language'] = 'German'

    # Intake semester
    intakes = []
    if 'winter semester' in text:
        intakes.append('winter')
    if 'summer semester' in text:
        intakes.append('summer')
    if intakes:
        info['start_semesters'] = intakes

    return info


def extract_all(html_path: str) -> Dict[str, Any]:
    """
    Main extraction function - extracts all content types from an HTML file
    Returns a comprehensive dictionary of extracted content
    """
    soup = load_html(html_path)
    main_content = extract_main_content(soup)

    if not main_content:
        main_content = soup

    return {
        'metadata': extract_metadata(soup),
        'full_text': extract_text(main_content),
        'headings': extract_headings(main_content),
        'sections': extract_sections(main_content),
        'lists': extract_lists(main_content),
        'tables': extract_tables(main_content),
        'links': extract_links(main_content),
        'program_info': extract_program_info(main_content),
    }


# Utility functions for common data cleaning

def clean_whitespace(text: str) -> str:
    """Remove excessive whitespace from text"""
    return re.sub(r'\s+', ' ', text).strip()


def extract_email(text: str) -> Optional[str]:
    """Extract email address from text"""
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    return match.group(0) if match else None


def extract_date(text: str) -> Optional[str]:
    """Extract dates in common formats (DD.MM.YYYY, Month DD, etc.)"""
    # German format: DD.MM.YYYY or DD.MM.
    match = re.search(r'\d{1,2}\.\d{1,2}\.(?:\d{4})?', text)
    if match:
        return match.group(0)

    # English format: Month DD or Month DD, YYYY
    match = re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,\s+\d{4})?', text, re.I)
    if match:
        return match.group(0)

    return None
