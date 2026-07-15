from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List
from urllib.parse import urlparse

import psycopg

from app.email.disclaimer import append_disclaimer_to_draft
from app.email.programme_guard import (
    build_unconfirmed_programme_draft,
    extract_unmatched_programme_name,
)
from app.email.multitopic import (
    add_reference_links_to_draft,
    build_evidence_query,
    build_followup_flag_message,
    clean_staff_draft,
    detect_topics,
    extract_email_context,
    filter_docs_for_programme,
    fix_application_fee_confusion,
    prepare_docs_for_staff_ui,
)
from app.email.thread_memory import (
    build_thread_key,
    classify_followup_email,
    load_thread_context,
    merge_context_with_thread,
    save_thread_context,
)
from app.knowledge.programme_context import (
    enrich_email_text_with_programme_context,
)
from app.knowledge.programme_official_evidence import (
    get_official_programme_docs,
)
from app.retrieval.baseline_adapter import (
    deduplicate_documents,
    retrieve_for_topic,
)
from app.retrieval.conflict import (
    detect_and_resolve_conflicts,
)
from app.runtime.local_llm import (
    HTWOllamaClient,
    build_email_system_prompt,
    build_email_user_prompt,
)
from app.settings import settings
from app.validation.email_validator import (
    validate_email_draft,
)


logger = logging.getLogger(__name__)


def _document_key(document: Dict[str, Any]) -> str:
    """
    Build a stable key used to deduplicate evidence across topics.
    """
    url = str(
        document.get("source_url")
        or document.get("url")
        or ""
    ).strip().lower().rstrip("/")

    if url:
        return f"url::{url}"

    identifier = str(
        document.get("id")
        or document.get("object_id")
        or ""
    ).strip()

    if identifier:
        return f"id::{identifier}"

    content = str(
        document.get("content")
        or document.get("chunk_text")
        or ""
    )

    return f"content::{content[:250].lower()}"


def _normalised_url_parts(url: str) -> tuple[str, str]:
    """
    Return a normalised host and path for programme-page matching.

    The scheme, query string and fragments are ignored. Language-only
    roots such as /en and /de are treated as the programme homepage.
    """
    raw_url = str(url or "").strip()

    if not raw_url:
        return "", ""

    parsed = urlparse(raw_url)
    host = parsed.netloc.lower().split("@")[-1].split(":")[0]

    if host.startswith("www."):
        host = host[4:]

    path = re.sub(
        r"/+",
        "/",
        parsed.path.lower(),
    ).rstrip("/")

    if path in {"/en", "/de"}:
        path = ""

    return host, path


def _document_url(document: Dict[str, Any]) -> str:
    return str(
        document.get("source_url")
        or document.get("url")
        or ""
    ).strip()


def _programme_hosts(
    email_context: Dict[str, Any],
) -> set[str]:
    hosts: set[str] = set()

    for key in (
        "target_program_url",
        "target_programme_url",
        "matched_programme_url",
        "target_program_application_url",
    ):
        host, _ = _normalised_url_parts(
            str(email_context.get(key) or "")
        )

        if host:
            hosts.add(host)

    return hosts


def _programme_title_tokens(
    email_context: Dict[str, Any],
) -> List[str]:
    programme_name = str(
        email_context.get("target_programme")
        or email_context.get("target_program")
        or email_context.get("matched_programme")
        or ""
    ).lower()

    ignored = {
        "and",
        "the",
        "of",
        "in",
        "master",
        "masters",
        "bachelor",
        "programme",
        "program",
    }

    return [
        token
        for token in re.findall(
            r"[a-z0-9]+",
            programme_name,
        )
        if len(token) > 2 and token not in ignored
    ]


def _select_programme_main_page(
    documents: List[Dict[str, Any]],
    email_context: Dict[str, Any],
) -> Dict[str, Any] | None:
    """
    Select the strongest programme homepage from all available candidates.

    This prevents a generic HTW page from replacing the direct programme
    page needed for language-of-instruction and study-format questions.
    """
    expected_hosts = _programme_hosts(email_context)
    title_tokens = _programme_title_tokens(email_context)

    best_document: Dict[str, Any] | None = None
    best_score = -1

    for document in documents:
        url = _document_url(document)
        host, path = _normalised_url_parts(url)

        if not host or host not in expected_hosts:
            continue

        # Application and subpages are useful evidence, but they are not
        # the programme homepage required by this selector.
        if any(
            part in path
            for part in (
                "/applying",
                "/application",
                "/apply",
                "/admission",
                "/faq",
                "/contact",
            )
        ):
            continue

        title = str(document.get("title") or "").lower()
        object_type = str(
            document.get("object_type") or ""
        ).lower()

        score = 0

        if path in {"", "/index.php", "/home"}:
            score += 8
        elif path.count("/") <= 1:
            score += 4

        if object_type in {
            "official_programme_page_cache",
            "programme_official_page",
            "canonical_programme_object",
        }:
            score += 6

        token_matches = sum(
            1 for token in title_tokens if token in title
        )
        score += min(token_matches, 4)

        if score > best_score:
            best_score = score
            best_document = document

    return best_document


def _select_programme_applying_page(
    documents: List[Dict[str, Any]],
    email_context: Dict[str, Any],
) -> Dict[str, Any] | None:
    """
    Select the strongest direct programme application page.
    """
    expected_hosts = _programme_hosts(email_context)

    best_document: Dict[str, Any] | None = None
    best_score = -1

    for document in documents:
        url = _document_url(document)
        host, path = _normalised_url_parts(url)

        if not host or host not in expected_hosts:
            continue

        title = str(document.get("title") or "").lower()
        object_type = str(
            document.get("object_type") or ""
        ).lower()

        if not (
            "apply" in path
            or "applying" in path
            or "application" in path
            or "applying" in title
            or "application" in title
        ):
            continue

        score = 0

        if object_type in {
            "official_programme_page_cache",
            "programme_official_page",
            "canonical_programme_object",
        }:
            score += 6

        if "applying" in title:
            score += 4

        if "applying" in path or "application" in path:
            score += 4

        if score > best_score:
            best_score = score
            best_document = document

    return best_document


def _append_unique_document(
    target: List[Dict[str, Any]],
    seen_keys: set[str],
    document: Dict[str, Any] | None,
) -> None:
    if document is None:
        return

    key = _document_key(document)

    if key in seen_keys:
        return

    target.append(document)
    seen_keys.add(key)


def _clean_email_structure(draft: str) -> str:
    """
    Remove a model-generated subject line and duplicate greetings.

    The email subject is handled separately by Gmail/n8n and must not
    appear inside the message body.
    """
    lines = [
        line.rstrip()
        for line in str(draft or "").splitlines()
    ]

    lines = [
        line
        for line in lines
        if not re.match(
            r"^\s*subject\s*:",
            line,
            flags=re.IGNORECASE,
        )
    ]

    greeting_pattern = re.compile(
        r"^\s*("
        r"dear\s+[^,]+,?|"
        r"guten\s+tag\s+[^,]+,?|"
        r"sehr\s+geehrte[rn]?\s+.+"
        r")\s*$",
        flags=re.IGNORECASE,
    )

    greeting_indexes = [
        index
        for index, line in enumerate(lines[:10])
        if greeting_pattern.match(line)
    ]

    if len(greeting_indexes) > 1:
        greeting_to_keep = greeting_indexes[-1]

        lines = [
            line
            for index, line in enumerate(lines)
            if (
                index == greeting_to_keep
                or index not in greeting_indexes
            )
        ]

    cleaned = "\n".join(lines)

    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned,
    )

    return cleaned.strip()


def _remove_unasked_topic_content(
    draft: str,
    topics: List[Dict[str, Any]],
) -> str:
    """
    Remove application-route advice when that topic was not detected.
    """
    topic_ids = {
        str(topic.get("topic_id") or "")
        for topic in topics
    }

    if (
        "application_route" in topic_ids
        or "application_process" in topic_ids
    ):
        return draft

    patterns = [
        (
            r"Please note that applications are accepted only "
            r"via the HTW application portal or uni-assist, "
            r"depending on your eligibility criteria\.?\s*"
        ),
        (
            r"Applications are accepted only via the HTW "
            r"application portal or uni-assist, depending on "
            r"your eligibility criteria\.?\s*"
        ),
    ]

    cleaned = str(draft or "")

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned,
    )

    return cleaned.strip()


def _document_text(document: Dict[str, Any]) -> str:
    """
    Combine source fields for deterministic support checks.
    """
    return " ".join(
        [
            str(document.get("title") or ""),
            str(document.get("content") or ""),
            str(document.get("chunk_text") or ""),
            str(document.get("source_url") or ""),
            str(document.get("url") or ""),
        ]
    ).lower()


def _citation_numbers(text: str) -> List[int]:
    return [
        int(number)
        for number in re.findall(
            r"\[Doc\s+(\d+)\]",
            text,
            flags=re.IGNORECASE,
        )
    ]


def _find_claim_support_issues(
    draft: str,
    documents: List[Dict[str, Any]],
) -> List[str]:
    """
    Check selected high-risk claims against the sources cited in the
    same paragraph.

    Regex patterns are used so wording variations cannot bypass the
    language-of-instruction and study-format checks.
    """
    rules = [
        {
            "claim_name": "language_of_instruction",
            "claim_regexes": (
                r"\blanguage of instruction\b.*?\bis english\b",
                r"\bprogramme\b.*?\b(?:is|is primarily|is entirely)\b"
                r".*?\btaught\b.*?\bin english\b",
                r"\bprogram\b.*?\b(?:is|is primarily|is entirely)\b"
                r".*?\btaught\b.*?\bin english\b",
                r"\btaught\b.*?\bin english\b",
            ),
            "support_patterns": (
                "language of instruction",
                "taught entirely in english",
                "taught in english",
                "english-taught",
                "english taught",
                "english-language programme",
                "english language programme",
                "teaching language",
            ),
        },
        {
            "claim_name": "study_format",
            "claim_regexes": (
                r"\b(?:programme|program)\b.*?\b(?:is|offered|delivered)\b"
                r".*?\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                r"\b(?:offered|delivered)\b.*?"
                r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
            ),
            "support_patterns": (
                "on-campus",
                "on campus",
                "online programme",
                "online program",
                "hybrid",
                "distance learning",
                "presence-based",
                "campus-based",
                "study format",
                "mode of study",
            ),
        },
    ]

    issues: List[str] = []

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(
            r"\n\s*\n",
            str(draft or ""),
        )
        if paragraph.strip()
    ]

    for paragraph in paragraphs:
        lower_paragraph = paragraph.lower()

        for rule in rules:
            has_claim = any(
                re.search(
                    pattern,
                    lower_paragraph,
                    flags=re.IGNORECASE | re.DOTALL,
                )
                for pattern in rule["claim_regexes"]
            )

            if not has_claim:
                continue

            # A cautious statement such as:
            # "The information does not explicitly confirm whether the
            # programme is on-campus, online, or hybrid"
            # is not an affirmative study-format claim.
            #
            # Without this exception, the validator sees the words
            # "on-campus", "online" or "hybrid" and incorrectly marks the
            # sentence as an unsupported factual claim.
            if rule["claim_name"] == "study_format":
                uncertainty_phrases = (
                    "does not explicitly confirm whether",
                    "does not confirm whether",
                    "could not be confirmed",
                    "cannot be confirmed",
                    "is not explicitly stated",
                    "is not stated in the available sources",
                    "available official sources do not confirm",
                    "information provided does not explicitly confirm",
                    "available information does not explicitly confirm",
                )

                contradictory_claim_patterns = (
                    r"\bbut\b[^.]{0,120}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                    r"\bhowever\b[^.]{0,120}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                    r"\bnevertheless\b[^.]{0,120}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                    r"\bprobably\b[^.]{0,100}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                    r"\blikely\b[^.]{0,100}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                    r"\bprimarily\b[^.]{0,100}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                    r"\bappears to be\b[^.]{0,100}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                    r"\bseems to be\b[^.]{0,100}"
                    r"\b(?:on[- ]campus|online|hybrid|distance learning)\b",
                )

                is_uncertainty_statement = any(
                    phrase in lower_paragraph
                    for phrase in uncertainty_phrases
                )

                also_makes_affirmative_claim = any(
                    re.search(
                        pattern,
                        lower_paragraph,
                        flags=re.IGNORECASE | re.DOTALL,
                    )
                    for pattern in contradictory_claim_patterns
                )

                if (
                    is_uncertainty_statement
                    and not also_makes_affirmative_claim
                ):
                    continue

            cited_numbers = _citation_numbers(paragraph)

            if not cited_numbers:
                issues.append(
                    f"{rule['claim_name']}: factual claim has no citation"
                )
                continue

            supported = False

            for number in cited_numbers:
                index = number - 1

                if index < 0 or index >= len(documents):
                    continue

                cited_text = _document_text(
                    documents[index]
                )

                if any(
                    support_pattern in cited_text
                    for support_pattern in rule[
                        "support_patterns"
                    ]
                ):
                    supported = True
                    break

            if not supported:
                issues.append(
                    f"{rule['claim_name']}: cited source does not "
                    "directly support the claim"
                )

    return list(dict.fromkeys(issues))


def _find_audience_issues(draft: str) -> List[str]:
    """
    Detect drafts that are incorrectly addressed to HTW staff instead
    of being written as a direct reply to the student.
    """
    lower_draft = str(draft or "").lower()

    problematic_phrases = (
        "dear htw berlin staff",
        "dear staff members",
        "dear htw staff",
        "i am writing on behalf of",
        "below are his questions",
        "below are her questions",
    )

    if any(
        phrase in lower_draft
        for phrase in problematic_phrases
    ):
        return [
            "wrong_audience: draft must be addressed directly "
            "to the student"
        ]

    return []


def _build_strengthened_system_prompt() -> str:
    """
    Extend the shared model prompt with deterministic email and
    source-to-claim rules. This works with local Mistral and HTW Qwen.
    """
    extra_rules = """

EMAIL FORMAT RULES:
- Write the reply directly to the student or applicant. Never address HTW staff and never say that you are writing on behalf of the student.
- Do not write a Subject line inside the email body.
- Use exactly one greeting.
- Use exactly one closing.
- Do not add application-route advice unless application_route or application_process is listed among the detected topics.

SOURCE-TO-CLAIM RULES:
- Cite the specific document that directly supports each factual claim.
- Do not cite an application page for study-format information unless that page explicitly states the study format.
- Do not treat a requirement for English-language proof as evidence that the programme is taught entirely in English.
- Do not state that a programme is on-campus, online, hybrid, full-time or part-time unless a cited document explicitly supports that description.
- It is acceptable to use cautious wording when a detail is not explicitly confirmed.
""".strip()

    return (
        build_email_system_prompt().rstrip()
        + "\n\n"
        + extra_rules
    )


class EmailAssistantService:
    def __init__(self, connection: psycopg.Connection) -> None:
        self.connection = connection
        self.llm = HTWOllamaClient()

    async def process_email(
        self,
        *,
        email_text: str,
        student_email: str | None = None,
        subject: str | None = None,
        thread_id: str | None = None,
        email_id: str | None = None,
        language: str | None = None,
        top_k: int = 6,
    ) -> Dict[str, Any]:
        overall_start = time.perf_counter()
        timing: Dict[str, float] = {}

        if not email_text or not email_text.strip():
            raise ValueError("email_text must not be empty")

        email_text = email_text.strip()

        if len(email_text) > settings.max_email_characters:
            raise ValueError(
                "Email exceeds the maximum permitted length"
            )

        thread_key = build_thread_key(
            thread_id=thread_id,
            student_email=student_email,
            subject=subject,
        )

        previous_context = (
            load_thread_context(thread_key)
            if settings.thread_memory_enabled
            else None
        )

        # -------------------------------------------------------------
        # Follow-up classification
        # -------------------------------------------------------------

        followup_start = time.perf_counter()

        followup_type = classify_followup_email(
            email_text,
            has_thread_memory=bool(previous_context),
        )

        timing["followup_detection"] = (
            time.perf_counter() - followup_start
        )

        # Complaints or requests to clarify a disputed previous answer
        # are routed directly to staff rather than answered automatically.
        if followup_type == "clarification_or_complaint":
            draft = build_followup_flag_message(email_text)
            draft = append_disclaimer_to_draft(draft)

            timing["total"] = (
                time.perf_counter() - overall_start
            )

            return {
                "is_followup": True,
                "followup_type": followup_type,
                "flagged_for_human": True,
                "thread_id": thread_key,
                "email_id": email_id,
                "email_context": {},
                "detected_topics": [],
                "staff_draft": draft,
                "citations": [],
                "sources": [],
                "validation": {
                    "is_grounded": False,
                    "citations_valid": False,
                    "has_hallucinations": False,
                    "confidence": 0.0,
                    "failure_type": (
                        "followup_requires_human_review"
                    ),
                },
                "quality": {
                    "quality_score": 0,
                    "quality_label": "review",
                    "review_required": True,
                    "review_reason": (
                        "Clarification or complaint requires "
                        "direct staff review"
                    ),
                    "citation_count": 0,
                    "citations": [],
                },
                "conflicts": [],
                "timing": timing,
                "automatic_send": False,
            }

        # -------------------------------------------------------------
        # Programme matching and context enrichment
        # -------------------------------------------------------------

        programme_start = time.perf_counter()

        programme_match = enrich_email_text_with_programme_context(
            email_text=email_text,
            subject=subject or "",
        )

        enriched_email = programme_match.get(
            "enriched_email_text",
            email_text,
        )

        timing["programme_matching"] = (
            time.perf_counter() - programme_start
        )

        # -------------------------------------------------------------
        # Context extraction and multi-topic detection
        # -------------------------------------------------------------

        context_start = time.perf_counter()

        email_context = extract_email_context(enriched_email)

        # Preserve request metadata for later draft formatting and n8n.
        email_context["original_subject"] = subject or ""
        email_context["student_email"] = student_email or ""
        email_context["requested_language"] = language or ""

        matched_programme = str(
            programme_match.get("program_name")
            or programme_match.get("matched_programme")
            or ""
        ).strip()

        # Detect a specific programme title from natural wording only when
        # the official HTW catalogue did not return a confirmed match.
        programme_candidate = ""

        if not matched_programme:
            programme_candidate = extract_unmatched_programme_name(
                email_text
            )

        if matched_programme:
            email_context["target_program"] = matched_programme
            email_context["target_programme"] = matched_programme
            email_context["matched_programme"] = matched_programme

        matched_url = str(
            programme_match.get("url") or ""
        ).strip()

        if matched_url:
            email_context["target_program_url"] = matched_url
            email_context["matched_programme_url"] = matched_url

        application_url = str(
            programme_match.get("application_url") or ""
        ).strip()

        if application_url:
            email_context[
                "target_program_application_url"
            ] = application_url

        # Merge prior context first. A newly stated unknown programme must then
        # override an older programme retained in thread memory.
        email_context = merge_context_with_thread(
            email_context,
            previous_context,
        )

        programme_context_keys = (
            "target_program",
            "target_programme",
            "matched_programme",
            "target_program_url",
            "target_programme_url",
            "matched_programme_url",
            "target_program_application_url",
            "matched_programme_application_url",
            "target_program_match_score",
            "target_program_source",
            "catalog_degree",
            "catalog_language",
            "catalog_study_format",
        )

        if matched_programme:
            email_context["programme_status"] = "confirmed"
            email_context["programme_mentioned"] = matched_programme

        elif programme_candidate:
            # Do not let fallback extraction or thread memory turn an
            # unconfirmed title into a programme match.
            for key in programme_context_keys:
                email_context.pop(key, None)

            email_context["programme_status"] = "unknown"
            email_context["programme_mentioned"] = programme_candidate

        elif (
            email_context.get("target_program")
            or email_context.get("matched_programme")
        ):
            inherited_programme = str(
                email_context.get("target_program")
                or email_context.get("matched_programme")
                or ""
            ).strip()

            email_context["programme_status"] = "confirmed"
            email_context["programme_mentioned"] = (
                inherited_programme or None
            )

        else:
            email_context["programme_status"] = "not_provided"
            email_context["programme_mentioned"] = None

        topics = detect_topics(
            enriched_email,
            email_context,
            max_topics=6,
        )

        timing["context_and_topics"] = (
            time.perf_counter() - context_start
        )

        # Hard stop before retrieval and generation. The system must not attach
        # generic Master's deadlines to a programme absent from the catalogue.
        if email_context.get("programme_status") == "unknown":
            requested_language = str(language or "").lower()

            reply_language = (
                "de"
                if requested_language.startswith("de")
                else "en"
            )

            safe_draft = build_unconfirmed_programme_draft(
                programme_name=programme_candidate,
                reply_language=reply_language,
            )

            safe_draft = append_disclaimer_to_draft(
                safe_draft
            )

            safe_topics: List[Dict[str, Any]] = []

            for topic in topics:
                safe_topic = dict(topic)
                safe_topic["query"] = (
                    safe_topic.get("base_query")
                    or safe_topic.get("query")
                    or email_text
                )
                safe_topic["official_source_count"] = 0
                safe_topic["retrieved_source_count"] = 0
                safe_topic["source_count"] = 0
                safe_topics.append(safe_topic)

            quality = {
                "quality_score": 75,
                "quality_label": "review",
                "review_required": True,
                "review_reason": (
                    "Programme named by the student was not "
                    "confirmed in the HTW programme catalogue"
                ),
                "citation_count": 0,
                "citations": [],
            }

            if settings.thread_memory_enabled:
                save_thread_context(
                    thread_key,
                    student_email=student_email,
                    subject=subject,
                    email_context=email_context,
                    detected_topics=safe_topics,
                    staff_draft=safe_draft,
                    quality=quality,
                )

            timing["total"] = (
                time.perf_counter() - overall_start
            )

            return {
                "is_followup": (
                    followup_type != "new_enquiry"
                ),
                "followup_type": followup_type,
                "flagged_for_human": True,
                "thread_id": thread_key,
                "email_id": email_id,
                "email_context": email_context,
                "detected_topics": safe_topics,
                "staff_draft": safe_draft,
                "citations": [],
                "sources": [],
                "validation": {
                    "is_grounded": False,
                    "citations_valid": False,
                    "has_hallucinations": False,
                    "confidence": 0.0,
                    "failure_type": "programme_not_confirmed",
                },
                "quality": quality,
                "conflicts": [],
                "timing": timing,
                "automatic_send": False,
            }

        # -------------------------------------------------------------
        # Topic-specific retrieval
        # -------------------------------------------------------------

        retrieval_start = time.perf_counter()

        all_documents: List[Dict[str, Any]] = []
        all_candidate_documents: List[Dict[str, Any]] = []
        topic_results: List[Dict[str, Any]] = []
        topic_document_groups: List[List[Dict[str, Any]]] = []

        for topic in topics:
            topic_id = str(
                topic.get("topic_id") or ""
            ).strip()

            base_query = (
                topic.get("base_query")
                or topic.get("query")
                or email_text
            )

            evidence_query = build_evidence_query(
                topic_id,
                base_query,
                email_context,
            )

            retrieved_documents = retrieve_for_topic(
                connection=self.connection,
                query=evidence_query,
                top_k=max(top_k, 5),
            )

            # The actual function signature is:
            # get_official_programme_docs(context, topic_id, limit=3)
            official_documents = get_official_programme_docs(
                email_context,
                topic_id,
                3,
            )

            # Programme-specific official evidence is deliberately placed
            # before generic vector-retrieval results.
            combined_documents = (
                official_documents + retrieved_documents
            )

            all_candidate_documents.extend(
                combined_documents
            )

            filtered_documents = filter_docs_for_programme(
                combined_documents,
                email_context,
                topic_id=topic_id,
                min_keep=3,
            )

            topic_result = dict(topic)
            topic_result["query"] = evidence_query
            topic_result["official_source_count"] = len(
                official_documents
            )
            topic_result["retrieved_source_count"] = len(
                retrieved_documents
            )
            topic_result["source_count"] = len(
                filtered_documents
            )

            topic_results.append(topic_result)
            topic_document_groups.append(filtered_documents)
            all_documents.extend(filtered_documents)

        # Preserve the direct programme application page and homepage
        # before adding topic-specific and generic backup evidence.
        programme_applying_page = _select_programme_applying_page(
            all_candidate_documents,
            email_context,
        )

        programme_main_page = _select_programme_main_page(
            all_candidate_documents,
            email_context,
        )

        mandatory_documents: List[Dict[str, Any]] = []
        mandatory_keys: set[str] = set()

        _append_unique_document(
            mandatory_documents,
            mandatory_keys,
            programme_applying_page,
        )

        topic_ids = {
            str(topic.get("topic_id") or "")
            for topic in topic_results
        }

        if topic_ids.intersection(
            {
                "language_of_instruction",
                "study_format",
                "programme_overview",
            }
        ):
            _append_unique_document(
                mandatory_documents,
                mandatory_keys,
                programme_main_page,
            )

        # Preserve at least one strongest unique source for each topic.
        priority_documents: List[Dict[str, Any]] = []
        remaining_documents: List[Dict[str, Any]] = []
        seen_candidate_keys: set[str] = set(
            mandatory_keys
        )

        for document_group in topic_document_groups:
            if not document_group:
                continue

            strongest_document: Dict[str, Any] | None = None

            for candidate in document_group:
                candidate_key = _document_key(candidate)

                if candidate_key not in seen_candidate_keys:
                    strongest_document = candidate
                    break

            if strongest_document is not None:
                _append_unique_document(
                    priority_documents,
                    seen_candidate_keys,
                    strongest_document,
                )

            for additional_document in document_group:
                _append_unique_document(
                    remaining_documents,
                    seen_candidate_keys,
                    additional_document,
                )

        candidate_documents = (
            mandatory_documents
            + priority_documents
            + remaining_documents
        )

        candidate_documents = deduplicate_documents(
            candidate_documents,
            limit=max(
                settings.final_source_limit * 3,
                15,
            ),
        )

        resolved_documents, conflicts = (
            detect_and_resolve_conflicts(candidate_documents)
        )

        # The conflict resolver must not accidentally remove complementary
        # programme pages such as the homepage and the applying page.
        resolved_by_key = {
            _document_key(document): document
            for document in resolved_documents
        }

        ordered_documents: List[Dict[str, Any]] = []
        ordered_keys: set[str] = set()

        for mandatory_document in mandatory_documents:
            mandatory_key = _document_key(
                mandatory_document
            )

            _append_unique_document(
                ordered_documents,
                ordered_keys,
                resolved_by_key.get(
                    mandatory_key,
                    mandatory_document,
                ),
            )

        for document in resolved_documents:
            _append_unique_document(
                ordered_documents,
                ordered_keys,
                document,
            )

        final_documents = ordered_documents[
            : settings.final_source_limit
        ]

        timing["retrieval"] = (
            time.perf_counter() - retrieval_start
        )

        # -------------------------------------------------------------
        # Staff-draft generation with the HTW-hosted Qwen model
        # -------------------------------------------------------------

        generation_start = time.perf_counter()

        if final_documents:
            user_prompt = build_email_user_prompt(
                original_email=email_text,
                email_context=email_context,
                topics=topic_results,
                documents=final_documents,
            )

            draft = await self.llm.generate(
                system_prompt=_build_strengthened_system_prompt(),
                user_prompt=user_prompt,
                temperature=0.1,
            )
        else:
            draft = (
                "Dear applicant,\n\n"
                "Thank you for your enquiry.\n\n"
                "I could not confirm the requested information "
                "from the available official sources. "
                "Please review this enquiry manually before "
                "replying.\n\n"
                "Kind regards,\n"
                "HTW Berlin Student Services"
            )

        draft = clean_staff_draft(
            draft,
            email_context,
        )

        draft = _clean_email_structure(draft)

        draft = _remove_unasked_topic_content(
            draft,
            topic_results,
        )

        draft = fix_application_fee_confusion(
            draft,
            topic_results,
            final_documents,
            email_context,
        )

        draft, display_documents = prepare_docs_for_staff_ui(
            draft=draft,
            docs=final_documents,
            context=email_context,
            max_sources=settings.final_source_limit,
        )

        draft = add_reference_links_to_draft(
            draft,
            display_documents,
            topic_results,
            email_context,
        )

        timing["generation"] = (
            time.perf_counter() - generation_start
        )

        # -------------------------------------------------------------
        # Citation, grounding and review validation
        # -------------------------------------------------------------

        validation_start = time.perf_counter()

        validation = validate_email_draft(
            draft=draft,
            documents=display_documents,
            topics=topic_results,
            email_context=email_context,
        )

        claim_support_issues = _find_claim_support_issues(
            draft,
            display_documents,
        )

        audience_issues = _find_audience_issues(draft)

        deterministic_issues = (
            claim_support_issues + audience_issues
        )

        if deterministic_issues:
            validation["is_grounded"] = False
            validation["citations_valid"] = False
            validation["has_hallucinations"] = bool(
                claim_support_issues
            )
            validation["confidence"] = min(
                float(validation.get("confidence", 0.0)),
                0.6 if claim_support_issues else 0.5,
            )
            validation["failure_type"] = (
                "wrong_audience"
                if audience_issues and not claim_support_issues
                else "claim_source_mismatch"
            )
            validation["review_required"] = True
            validation["review_reason"] = "; ".join(
                deterministic_issues
            )

        validation_review_required = bool(
            validation.get("review_required", False)
        )

        review_required = (
            validation_review_required
            or settings.staff_review_required_for_all
        )

        review_reasons: List[str] = []

        validation_reason = str(
            validation.get("review_reason") or ""
        ).strip()

        if validation_reason:
            review_reasons.append(validation_reason)

        if settings.staff_review_required_for_all:
            review_reasons.append(
                "All HANS drafts require staff review "
                "before sending"
            )

        # Remove duplicate review reasons while preserving order.
        review_reason = "; ".join(
            dict.fromkeys(review_reasons)
        )

        quality_score = round(
            float(validation.get("confidence", 0.0))
            * 100
        )

        # The quality label represents content quality. A good draft may
        # still require staff review because production is draft-only.
        quality_label = (
            "review"
            if validation_review_required
            else "good"
        )

        draft = append_disclaimer_to_draft(draft)

        timing["validation"] = (
            time.perf_counter() - validation_start
        )

        quality = {
            "quality_score": quality_score,
            "quality_label": quality_label,
            "review_required": review_required,
            "review_reason": review_reason,
            "citation_count": int(
                validation.get("citation_count", 0)
            ),
            "citations": list(
                validation.get("citations", [])
            ),
        }

        # -------------------------------------------------------------
        # Thread-memory update
        # -------------------------------------------------------------

        if settings.thread_memory_enabled:
            save_thread_context(
                thread_key,
                student_email=student_email,
                subject=subject,
                email_context=email_context,
                detected_topics=topic_results,
                staff_draft=draft,
                quality=quality,
            )

        timing["total"] = (
            time.perf_counter() - overall_start
        )

        # -------------------------------------------------------------
        # API-safe source representation
        # -------------------------------------------------------------

        sources: List[Dict[str, Any]] = []

        for document in display_documents:
            content = str(
                document.get("content")
                or document.get("chunk_text")
                or ""
            )

            sources.append(
                {
                    "id": str(
                        document.get("id")
                        or document.get("object_id")
                        or ""
                    ),
                    "title": str(
                        document.get("title") or ""
                    ),
                    "url": str(
                        document.get("source_url")
                        or document.get("url")
                        or ""
                    ),
                    "type": str(
                        document.get("object_type")
                        or ""
                    ),
                    "last_updated": str(
                        document.get("last_updated")
                        or document.get(
                            "metadata",
                            {},
                        ).get("retrieved_at", "")
                        or ""
                    ),
                    "excerpt": content[:300],
                }
            )

        return {
            "is_followup": (
                followup_type != "new_enquiry"
            ),
            "followup_type": followup_type,
            "flagged_for_human": review_required,
            "thread_id": thread_key,
            "email_id": email_id,
            "email_context": email_context,
            "detected_topics": topic_results,
            "staff_draft": draft,
            "citations": list(
                validation.get("citations", [])
            ),
            "sources": sources,
            "validation": {
                "is_grounded": bool(
                    validation.get(
                        "is_grounded",
                        False,
                    )
                ),
                "citations_valid": bool(
                    validation.get(
                        "citations_valid",
                        False,
                    )
                ),
                "has_hallucinations": bool(
                    validation.get(
                        "has_hallucinations",
                        False,
                    )
                ),
                "confidence": float(
                    validation.get(
                        "confidence",
                        0.0,
                    )
                ),
                "failure_type": validation.get(
                    "failure_type"
                ),
            },
            "quality": quality,
            "conflicts": conflicts,
            "timing": timing,
            "automatic_send": False,
        }