"""
Object Schema Definitions for HTW Scrape Project

This module defines the structure for all 13 object types used in the RAG/MCP system.
Each schema includes:
- Common metadata fields (page_id, url, title, classification info)
- Type-specific structured data fields
- Content fields (extracted text)
- Relationship fields (links to related objects)
"""

from typing import TypedDict, List, Optional, Dict, Any
from datetime import datetime


# ==============================================================================
# BASE SCHEMA (Common to all object types)
# ==============================================================================

class BaseMetadata(TypedDict):
    """Common metadata for all objects"""
    page_id: str                      # SHA-256 hash from scraping
    object_id: str                    # Slugified identifier for this object
    object_type: str                  # One of 13 classification types
    url: str                          # Source URL
    title: str                        # Page title
    classification_confidence: str    # high, medium, low
    classification_notes: str         # Human-written classification explanation
    source_html_path: str            # Path to raw HTML snapshot
    last_scraped: str                # ISO date when page was scraped
    last_processed: str              # ISO date when object was created


class ContentFields(TypedDict):
    """Extracted content from HTML"""
    full_text: str                   # Plain text, HTML stripped
    summary: Optional[str]           # Brief description if available
    sections: Optional[List[Dict]]   # Structured sections from page


# ==============================================================================
# 1. DEGREE_PROGRAM (10 pages)
# ==============================================================================

class DegreeProgramObject(TypedDict):
    """Schema for degree program landing pages"""
    metadata: BaseMetadata

    program_info: Dict[str, Any]     # name, degree_type, duration, ects, language, intake
    admission_requirements: Dict[str, Any]  # bachelor_degree, grades, language, additional
    curriculum: Dict[str, Any]       # core_modules, elective_page_ref, thesis, internship
    application_info: Dict[str, Any] # route, portal, deadlines, fees

    related_pages: List[str]         # Object IDs of related pages
    content: ContentFields


# ==============================================================================
# 2. CURRICULUM_PAGE (18 pages)
# ==============================================================================

class CurriculumPageObject(TypedDict):
    """Schema for course/module listings"""
    metadata: BaseMetadata

    curriculum_info: Dict[str, Any]  # program_ref, semester, module_type (core/elective)
    modules: List[Dict[str, Any]]    # List of courses with credits, descriptions

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 3. APPLICATION_PROCESS (18 pages)
# ==============================================================================

class ApplicationProcessObject(TypedDict):
    """Schema for application procedures and how-to guides"""
    metadata: BaseMetadata

    process_info: Dict[str, Any]     # name, applies_to, description
    steps: List[Dict[str, Any]]      # Ordered list of application steps
    deadlines: Optional[Dict[str, Any]]  # Key dates if mentioned
    requirements: Optional[Dict[str, Any]]  # Prerequisites
    fees: Optional[Dict[str, Any]]   # Application fees if applicable

    contact: Optional[Dict[str, Any]]  # Office, email, external links
    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 4. APPLICATION_ROUTE_RULE (23 pages)
# ==============================================================================

class ApplicationRouteRuleObject(TypedDict):
    """Schema for eligibility rules and external requirements (visa, documents, etc.)"""
    metadata: BaseMetadata

    rule_info: Dict[str, Any]        # rule_type, scope, applies_to, varies_by
    requirements: Dict[str, Any]     # Specific conditions and rules
    exceptions: Optional[List[str]]  # Cases where rule doesn't apply
    documentation: Optional[List[str]]  # Required documents

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 5. LANGUAGE_PROOF_RULE (8 pages)
# ==============================================================================

class LanguageProofRuleObject(TypedDict):
    """Schema for language requirement and certificate pages"""
    metadata: BaseMetadata

    language_info: Dict[str, Any]    # language, test_name, required_for
    requirement_details: Dict[str, Any]  # minimum_level, alternatives, exemptions
    test_details: Optional[Dict[str, Any]]  # sections, duration, registration

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 6. FEES_FUNDING_RULE (9 pages)
# ==============================================================================

class FeesFundingRuleObject(TypedDict):
    """Schema for cost, fees, and funding information"""
    metadata: BaseMetadata

    financial_info: Dict[str, Any]   # type (fee/funding), amount, currency, frequency
    eligibility: Optional[Dict[str, Any]]  # Who qualifies
    application_process: Optional[Dict[str, Any]]  # How to apply for funding
    deadlines: Optional[Dict[str, Any]]  # Payment or application deadlines

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 7. DEADLINE_RULE (2 pages)
# ==============================================================================

class DeadlineRuleObject(TypedDict):
    """Schema for deadline and academic calendar pages"""
    metadata: BaseMetadata

    deadline_info: Dict[str, Any]    # type, applies_to
    dates: Dict[str, Any]           # Specific dates and periods

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 8. OVERVIEW_NAVIGATION (38 pages)
# ==============================================================================

class OverviewNavigationObject(TypedDict):
    """Schema for hub/index pages that organize related content"""
    metadata: BaseMetadata

    navigation_info: Dict[str, Any]  # purpose, scope, audience
    sections: List[Dict[str, Any]]   # Organized list of subtopics
    child_pages: List[str]          # Object IDs of linked pages

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 9. SPECIAL_CATEGORY (31 pages)
# ==============================================================================

class SpecialCategoryObject(TypedDict):
    """Schema for time-bound, exceptional, or specialized content"""
    metadata: BaseMetadata

    category_info: Dict[str, Any]    # category_type, purpose, audience, time_bound
    details: Dict[str, Any]         # Category-specific information

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 10. ACCESSIBILITY_SUPPORT (12 pages)
# ==============================================================================

class AccessibilitySupportObject(TypedDict):
    """Schema for disability support and accessibility services"""
    metadata: BaseMetadata

    support_info: Dict[str, Any]     # service_type, who_for, scope
    services: List[Dict[str, Any]]   # Available support services
    contact: Optional[Dict[str, Any]]  # How to access support

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 11. FAQ_SUPPORT (3 pages)
# ==============================================================================

class FAQSupportObject(TypedDict):
    """Schema for FAQ pages"""
    metadata: BaseMetadata

    faq_info: Dict[str, Any]         # topic, audience
    questions: List[Dict[str, Any]]  # List of Q&A pairs

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 12. UNIVERSITY_PROFILE (1 page)
# ==============================================================================

class UniversityProfileObject(TypedDict):
    """Schema for institutional information pages"""
    metadata: BaseMetadata

    profile_info: Dict[str, Any]     # department, role, offerings

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# 13. FAMILY_SUPPORT (1 page)
# ==============================================================================

class FamilySupportObject(TypedDict):
    """Schema for family-related services and support"""
    metadata: BaseMetadata

    support_info: Dict[str, Any]     # service_type, who_for
    services: List[Dict[str, Any]]   # Available support
    contact: Optional[Dict[str, Any]]

    related_pages: List[str]
    content: ContentFields


# ==============================================================================
# SCHEMA REGISTRY
# ==============================================================================

OBJECT_SCHEMAS = {
    'degree_program': DegreeProgramObject,
    'curriculum_page': CurriculumPageObject,
    'application_process': ApplicationProcessObject,
    'application_route_rule': ApplicationRouteRuleObject,
    'language_proof_rule': LanguageProofRuleObject,
    'fees_funding_rule': FeesFundingRuleObject,
    'deadline_rule': DeadlineRuleObject,
    'overview_navigation': OverviewNavigationObject,
    'special_category': SpecialCategoryObject,
    'accessibility_support': AccessibilitySupportObject,
    'faq_support': FAQSupportObject,
    'university_profile': UniversityProfileObject,
    'family_support': FamilySupportObject,
}


def get_schema_for_type(object_type: str):
    """Get the schema class for a given object type"""
    return OBJECT_SCHEMAS.get(object_type)


def get_all_object_types() -> List[str]:
    """Return list of all valid object types"""
    return list(OBJECT_SCHEMAS.keys())
