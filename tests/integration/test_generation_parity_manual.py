from __future__ import annotations

import asyncio
import copy
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import app.email.service as service_module
from app.email.service import EmailAssistantService
from hansdb.conn import get_db_connection, load_config


ORIGINAL_EMAIL = """Dear Admissions Team,

I would like to apply for the Master's programme in
Project Management and Data Science.

Could you please tell me:

1. What is the application deadline?
2. Is the programme taught entirely in English?
3. Is it an on-campus programme?
4. Which application documents are required?

Kind regards,
Arjun"""

EXPECTED_TOPICS = {
    "application_deadline",
    "language_of_instruction",
    "study_format",
    "required_documents",
}


def _document_content(document: Dict[str, Any]) -> str:
    return str(
        document.get("content")
        or document.get("chunk_text")
        or ""
    )


def _document_url(document: Dict[str, Any]) -> str:
    return str(
        document.get("source_url")
        or document.get("url")
        or ""
    ).strip()


def _document_summary(
    document: Dict[str, Any],
    number: int,
) -> Dict[str, Any]:
    content = _document_content(document)

    return {
        "doc_number": number,
        "id": str(
            document.get("id")
            or document.get("object_id")
            or ""
        ),
        "title": str(document.get("title") or ""),
        "url": _document_url(document),
        "object_type": str(
            document.get("object_type")
            or document.get("type")
            or ""
        ),
        "score": document.get("score"),
        "last_updated": str(
            document.get("last_updated")
            or document.get("metadata", {}).get(
                "retrieved_at",
                "",
            )
            or ""
        ),
        "content_characters": len(content),
        "content_preview": content[:500],
    }


def _extract_signature_name(email_text: str) -> str:
    lines = [
        line.strip()
        for line in str(email_text or "").splitlines()
        if line.strip()
    ]

    closing_markers = {
        "kind regards",
        "best regards",
        "regards",
        "sincerely",
        "mit freundlichen grüßen",
        "freundliche grüße",
    }

    for index, line in enumerate(lines):
        if line.lower().rstrip(",") not in closing_markers:
            continue

        if index + 1 >= len(lines):
            continue

        candidate = lines[index + 1].strip()

        if re.fullmatch(
            r"[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-']{1,40}",
            candidate,
        ):
            return candidate

    return ""


def _build_poc_evidence(
    documents: List[Dict[str, Any]],
) -> str:
    """
    Reconstruct the final PoC's evidence formatting.

    The PoC placed up to 1,400 characters from each selected document
    into one final generation prompt.
    """
    blocks: List[str] = []

    for index, document in enumerate(documents, start=1):
        title = str(document.get("title") or "")
        url = _document_url(document)
        updated = str(document.get("last_updated") or "")
        content = _document_content(document)

        blocks.append(
            f"[Doc {index}] {title}\n"
            f"URL: {url}\n"
            f"Last updated: {updated}\n"
            f"CONTENT:\n{content[:1400]}"
        )

    return "\n\n---\n\n".join(blocks)


def _build_profile(
    context: Dict[str, Any],
) -> str:
    fields = [
        ("target_degree", "Target degree"),
        ("target_program", "Target programme"),
        ("target_program_url", "Programme page"),
        (
            "target_program_application_url",
            "Programme application page",
        ),
        ("catalog_degree", "Catalogue degree hint"),
        ("catalog_language", "Catalogue language hint"),
        (
            "catalog_study_format",
            "Catalogue study format hint",
        ),
        (
            "previous_degree",
            "Previous/current education",
        ),
        ("country", "Applicant background"),
        ("citizenship_group", "Citizenship category"),
        ("residence_country", "Residence country"),
    ]

    lines = [
        f"{label}: {context[key]}"
        for key, label in fields
        if context.get(key)
    ]

    return (
        "\n".join(lines)
        if lines
        else "No clear profile information detected."
    )


def _build_topics_text(
    topics: List[Dict[str, Any]],
) -> str:
    return "\n".join(
        (
            f"- {topic.get('label', '')}: "
            f"{topic.get('base_query') or topic.get('query') or ''}"
        )
        for topic in topics
    )


def _build_poc_system_prompt() -> str:
    """
    Reconstruct the concise final PoC system prompt.

    This intentionally does not include the later enhanced-deployment
    rules. The purpose is to isolate prompt behaviour while keeping the
    model and evidence constant.
    """
    return (
        "You are drafting an email from HTW Berlin Student Services "
        "to a student. "
        "Write in simple, polite and professional English. "
        "Use only the evidence documents. "
        "Do not invent information. "
        "Write directly to the student using 'you', not 'the student'. "
        "Keep the email ready to paste and send after staff review. "
        "Be specific and useful, but stay cautious where formal "
        "checking is required."
    )


def _build_poc_user_prompt(
    *,
    original_email: str,
    context: Dict[str, Any],
    topics: List[Dict[str, Any]],
    documents: List[Dict[str, Any]],
) -> str:
    profile = _build_profile(context)
    topics_text = _build_topics_text(topics)
    evidence = _build_poc_evidence(documents)

    name = (
        str(context.get("student_name") or "").strip()
        or _extract_signature_name(original_email)
    )
    greeting = f"Dear {name}," if name else "Dear applicant,"

    return (
        f"ORIGINAL STUDENT EMAIL:\n{original_email}\n\n"
        f"INTERPRETED STUDENT PROFILE:\n{profile}\n\n"
        f"TOPICS TO ANSWER ONLY:\n{topics_text}\n\n"
        f"EVIDENCE DOCUMENTS:\n{evidence}\n\n"
        "DRAFTING RULES:\n"
        "0) Write the complete draft in English.\n"
        "1) Start with the greeting provided below.\n"
        f"GREETING: {greeting}\n"
        "After the greeting, add one short polite opening sentence.\n"
        "2) Answer only the topics asked in the student email or "
        "listed above. Do not add additional topics from the evidence.\n"
        "3) Keep each topic to 1-3 short sentences.\n"
        "4) Do not use markdown headings, tables, or long bullet lists.\n"
        "5) Include separate citations immediately after factual claims, "
        "for example [Doc 1] [Doc 2]. Do not use grouped citations such "
        "as [Doc 1, Doc 2] or [Docs 1, 2].\n"
        "6) Use programme-specific evidence before general HTW pages "
        "when both are available.\n"
        "7) If the evidence does not explicitly confirm a requested "
        "detail, say that it could not be confirmed from the available "
        "official sources. Do not infer it from related wording.\n"
        "8) End with exactly:\n"
        "Kind regards,\n"
        "HTW Berlin Student Services"
    )


class CapturingLLM:
    def __init__(
        self,
        delegate: Any,
        capture: Dict[str, Any],
    ) -> None:
        self.delegate = delegate
        self.capture = capture

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> str:
        self.capture["enhanced_system_prompt"] = system_prompt
        self.capture["enhanced_user_prompt"] = user_prompt
        self.capture["enhanced_temperature"] = temperature

        output = await self.delegate.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            **kwargs,
        )

        self.capture["enhanced_raw_output"] = output
        return output


def _maximum_visible_prefix(
    content: str,
    prompt: str,
) -> int:
    """
    Estimate how much of a document's beginning is present verbatim in
    a prompt. This helps reveal prompt-level truncation.
    """
    if not content or not prompt:
        return 0

    candidate_lengths = [
        len(content),
        8000,
        6000,
        5000,
        4000,
        3000,
        2500,
        2000,
        1600,
        1400,
        1200,
        1000,
        800,
        600,
        500,
        400,
        300,
        200,
        100,
    ]

    for length in candidate_lengths:
        if length <= 0 or length > len(content):
            continue

        if content[:length] in prompt:
            return length

    return 0


def _keyword_snippets(
    text: str,
    keywords: List[str],
    radius: int = 170,
) -> List[Dict[str, str]]:
    lower = str(text or "").lower()
    snippets: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for keyword in keywords:
        start = 0

        while True:
            index = lower.find(keyword.lower(), start)

            if index < 0:
                break

            left = max(0, index - radius)
            right = min(len(text), index + len(keyword) + radius)
            snippet = re.sub(
                r"\s+",
                " ",
                text[left:right],
            ).strip()

            key = (keyword.lower(), snippet)

            if key not in seen:
                snippets.append(
                    {
                        "keyword": keyword,
                        "snippet": snippet,
                    }
                )
                seen.add(key)

            start = index + len(keyword)

            if len(snippets) >= 12:
                return snippets

    return snippets


def _split_email_body(text: str) -> str:
    value = str(text or "")

    for marker in (
        "Reference links for staff verification:",
        "Referenzlinks zur Prüfung durch Mitarbeitende:",
        "---\n\nThis draft response was generated",
    ):
        if marker in value:
            value = value.split(marker, 1)[0]

    return value.strip()


def _analyse_output(
    text: str,
    documents: List[Dict[str, Any]],
) -> Dict[str, Any]:
    body = _split_email_body(text)
    lower = body.lower()

    topic_checks = {
        "application_deadline": any(
            phrase in lower
            for phrase in (
                "application deadline",
                "application period",
                "1 may",
                "31 august",
            )
        ),
        "language_of_instruction": any(
            phrase in lower
            for phrase in (
                "language of instruction",
                "taught in english",
                "taught entirely in english",
                "english-taught",
            )
        ),
        "study_format": any(
            phrase in lower
            for phrase in (
                "study format",
                "on-campus",
                "on campus",
                "hybrid",
                "distance learning",
                "full-time",
                "part-time",
                "could not confirm",
                "not explicitly",
            )
        ),
        "required_documents": any(
            phrase in lower
            for phrase in (
                "required documents",
                "documents",
                "degree certificate",
                "grade transcript",
            )
        ),
    }

    grouped_citation_patterns = [
        r"\[Docs?\s+\d+\s*,",
        r"\[Docs?\s+\d+\s*(?:and|&)\s*\d+",
    ]

    unasked_content_flags = {
        "generic_selection_criteria": (
            "additional selection criteria" in lower
        ),
        "generic_application_portal_advice": (
            "application portal" in lower
        ),
        "scholarship_content": "scholarship" in lower,
        "application_route_content": any(
            phrase in lower
            for phrase in (
                "uni-assist",
                "hochschulstart",
                "application route",
            )
        ),
    }

    format_claim_flags = {
        "claims_on_campus": bool(
            re.search(r"\bon[- ]campus\b", lower)
        ),
        "claims_hybrid": "hybrid" in lower,
        "claims_online_programme": bool(
            re.search(
                r"\b(?:is|offered as|delivered as)\b.{0,30}"
                r"\bonline\b",
                lower,
            )
        ),
        "claims_full_time": bool(
            re.search(r"\bfull[- ]time\b", lower)
        ),
        "claims_part_time": bool(
            re.search(r"\bpart[- ]time\b", lower)
        ),
        "admits_not_explicitly_confirmed": any(
            phrase in lower
            for phrase in (
                "not explicitly confirmed",
                "could not be confirmed",
                "does not explicitly state",
                "available official sources do not confirm",
            )
        ),
    }

    combined_evidence = "\n".join(
        _document_content(document)
        for document in documents
    ).lower()

    explicit_evidence_terms = [
        "on-campus",
        "on campus",
        "campus-based",
        "presence-based",
        "hybrid programme",
        "hybrid program",
        "distance learning",
        "distance-learning",
        "full-time",
        "full time",
        "part-time",
        "part time",
        "online programme",
        "online program",
        "offered online",
    ]

    component_only_terms = [
        "self-paced online learning",
        "online learning",
        "lectures",
        "company visits",
        "case studies",
    ]

    explicit_mode_evidence = [
        term
        for term in explicit_evidence_terms
        if term in combined_evidence
    ]

    component_evidence = [
        term
        for term in component_only_terms
        if term in combined_evidence
    ]

    unsupported_format_risk = bool(
        (
            format_claim_flags["claims_on_campus"]
            or format_claim_flags["claims_hybrid"]
            or format_claim_flags["claims_online_programme"]
            or format_claim_flags["claims_full_time"]
            or format_claim_flags["claims_part_time"]
        )
        and not explicit_mode_evidence
    )

    return {
        "topic_checks": topic_checks,
        "topic_coverage_count": sum(topic_checks.values()),
        "grouped_citation_found": any(
            re.search(pattern, body, flags=re.IGNORECASE)
            for pattern in grouped_citation_patterns
        ),
        "unasked_content_flags": unasked_content_flags,
        "format_claim_flags": format_claim_flags,
        "explicit_mode_evidence_terms": explicit_mode_evidence,
        "component_level_evidence_terms": component_evidence,
        "unsupported_study_format_risk": unsupported_format_risk,
        "citation_numbers": sorted(
            {
                int(number)
                for number in re.findall(
                    r"\[Doc\s+(\d+)\]",
                    body,
                    flags=re.IGNORECASE,
                )
            }
        ),
    }


def _prompt_rule_checks(prompt: str) -> Dict[str, bool]:
    lower = str(prompt or "").lower()

    return {
        "use_only_evidence": (
            "use only" in lower and "evidence" in lower
        ),
        "do_not_invent": (
            "do not invent" in lower
            or "do not guess" in lower
        ),
        "answer_only_asked_topics": (
            "answer only" in lower
            and "topic" in lower
        ),
        "insufficient_evidence_fallback": any(
            phrase in lower
            for phrase in (
                "not sufficient",
                "not explicitly confirmed",
                "could not confirm",
                "insufficient evidence",
            )
        ),
        "separate_citation_rule": (
            "separate citations" in lower
            or "do not use grouped citations" in lower
        ),
        "direct_source_support_rule": any(
            phrase in lower
            for phrase in (
                "directly supports",
                "specific document",
                "specific source",
            )
        ),
        "no_study_format_inference_rule": any(
            phrase in lower
            for phrase in (
                "do not state that a programme is on-campus",
                "do not infer it from related wording",
                "unless a cited document explicitly supports",
            )
        ),
        "direct_to_student_rule": (
            "directly to the student" in lower
            or "using 'you'" in lower
        ),
    }


def _open_connection() -> Any:
    config = load_config()

    try:
        return get_db_connection(config)
    except TypeError:
        # Compatibility with a no-argument connection helper.
        return get_db_connection()


async def main() -> None:
    run_timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_directory = Path(
        "runtime_data/parity"
    )
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    capture: Dict[str, Any] = {}
    original_prompt_builder = (
        service_module.build_email_user_prompt
    )
    original_save_thread_context = (
        service_module.save_thread_context
    )

    def capture_prompt_builder(
        *args: Any,
        **kwargs: Any,
    ) -> str:
        prompt = original_prompt_builder(
            *args,
            **kwargs,
        )

        if kwargs:
            capture["email_context"] = copy.deepcopy(
                kwargs.get("email_context", {})
            )
            capture["topics"] = copy.deepcopy(
                kwargs.get("topics", [])
            )
            capture["documents"] = copy.deepcopy(
                kwargs.get("documents", [])
            )
            capture["original_email"] = str(
                kwargs.get("original_email", "")
            )

        capture["enhanced_user_prompt_from_builder"] = (
            prompt
        )
        return prompt

    connection = _open_connection()

    try:
        service_module.build_email_user_prompt = (
            capture_prompt_builder
        )

        # Keep this diagnostic read-only with respect to email thread
        # memory. Retrieval and generation still run normally.
        service_module.save_thread_context = (
            lambda *args, **kwargs: None
        )

        service = EmailAssistantService(connection)
        real_llm = service.llm
        service.llm = CapturingLLM(
            real_llm,
            capture,
        )

        enhanced_result = await service.process_email(
            email_text=ORIGINAL_EMAIL,
            student_email="arjun@example.com",
            subject="MPMD application questions",
            thread_id=(
                f"parity_mpmd_{run_timestamp}"
            ),
            email_id=f"parity-{run_timestamp}",
            language="en",
            top_k=6,
        )

    finally:
        service_module.build_email_user_prompt = (
            original_prompt_builder
        )
        service_module.save_thread_context = (
            original_save_thread_context
        )
        connection.close()

    documents = list(
        capture.get("documents", [])
    )
    topics = list(
        capture.get("topics", [])
    )
    context = dict(
        capture.get("email_context", {})
    )

    if not documents:
        raise RuntimeError(
            "The test could not capture the final generation "
            "documents. Check whether service.py still calls "
            "build_email_user_prompt(..., documents=final_documents)."
        )

    context_for_poc = copy.deepcopy(context)

    if not context_for_poc.get("student_name"):
        signature_name = _extract_signature_name(
            ORIGINAL_EMAIL
        )

        if signature_name:
            context_for_poc["student_name"] = (
                signature_name
            )

    poc_system_prompt = _build_poc_system_prompt()
    poc_user_prompt = _build_poc_user_prompt(
        original_email=ORIGINAL_EMAIL,
        context=context_for_poc,
        topics=topics,
        documents=documents,
    )

    # Same local model, same evidence, same temperature.
    poc_raw_output = await real_llm.generate(
        system_prompt=poc_system_prompt,
        user_prompt=poc_user_prompt,
        temperature=0.1,
    )

    enhanced_system_prompt = str(
        capture.get("enhanced_system_prompt", "")
    )
    enhanced_user_prompt = str(
        capture.get("enhanced_user_prompt", "")
    )
    enhanced_raw_output = str(
        capture.get("enhanced_raw_output", "")
    )
    enhanced_cleaned_output = str(
        enhanced_result.get("staff_draft", "")
    )

    document_summaries = [
        _document_summary(document, index)
        for index, document in enumerate(
            documents,
            start=1,
        )
    ]

    prompt_visibility: List[Dict[str, Any]] = []

    for index, document in enumerate(
        documents,
        start=1,
    ):
        content = _document_content(document)

        prompt_visibility.append(
            {
                "doc_number": index,
                "title": str(
                    document.get("title") or ""
                ),
                "full_content_characters": len(
                    content
                ),
                "estimated_prefix_in_enhanced_prompt": (
                    _maximum_visible_prefix(
                        content,
                        enhanced_user_prompt,
                    )
                ),
                "estimated_prefix_in_poc_prompt": (
                    _maximum_visible_prefix(
                        content,
                        poc_user_prompt,
                    )
                ),
            }
        )

    format_keywords = [
        "on-campus",
        "on campus",
        "campus-based",
        "presence-based",
        "hybrid",
        "online programme",
        "online program",
        "distance learning",
        "full-time",
        "full time",
        "part-time",
        "part time",
        "self-paced online learning",
        "online learning",
        "lectures",
        "company visits",
    ]

    evidence_format_audit = []

    for index, document in enumerate(
        documents,
        start=1,
    ):
        snippets = _keyword_snippets(
            _document_content(document),
            format_keywords,
        )

        if snippets:
            evidence_format_audit.append(
                {
                    "doc_number": index,
                    "title": str(
                        document.get("title") or ""
                    ),
                    "url": _document_url(document),
                    "matches": snippets,
                }
            )

    enhanced_topic_ids = {
        str(topic.get("topic_id") or "")
        for topic in topics
    }

    report: Dict[str, Any] = {
        "run_timestamp": run_timestamp,
        "purpose": (
            "Controlled generation parity test: same input, "
            "same enhanced-deployment evidence pack, same local "
            "LLM and temperature; only the generation prompt changes."
        ),
        "controlled_variables": {
            "original_email_same": True,
            "documents_same": True,
            "model_client_same": True,
            "temperature_same": True,
            "temperature": 0.1,
            "changed_variable": (
                "enhanced deployment prompt versus "
                "reconstructed final PoC email prompt"
            ),
        },
        "input": {
            "email_text": ORIGINAL_EMAIL,
            "student_email": "arjun@example.com",
            "subject": "MPMD application questions",
            "expected_topics": sorted(
                EXPECTED_TOPICS
            ),
        },
        "pipeline_capture": {
            "email_context": context,
            "topics": topics,
            "captured_topic_ids": sorted(
                enhanced_topic_ids
            ),
            "topic_match": (
                enhanced_topic_ids
                == EXPECTED_TOPICS
            ),
            "documents": document_summaries,
            "prompt_visibility": prompt_visibility,
            "evidence_format_audit": (
                evidence_format_audit
            ),
        },
        "baseline_prompt_principles_reviewed": [
            "Use only the retrieved context.",
            "State when the context is insufficient.",
            "Cite the supporting source.",
            "Keep the original user question separate from the context.",
            (
                "Pass sufficiently complete merged document content "
                "to generation rather than isolated fragments."
            ),
        ],
        "enhanced_deployment": {
            "system_prompt": enhanced_system_prompt,
            "user_prompt": enhanced_user_prompt,
            "system_prompt_characters": len(
                enhanced_system_prompt
            ),
            "user_prompt_characters": len(
                enhanced_user_prompt
            ),
            "prompt_rule_checks": (
                _prompt_rule_checks(
                    enhanced_system_prompt
                    + "\n"
                    + enhanced_user_prompt
                )
            ),
            "raw_model_output": enhanced_raw_output,
            "cleaned_service_output": (
                enhanced_cleaned_output
            ),
            "output_analysis_raw": _analyse_output(
                enhanced_raw_output,
                documents,
            ),
            "output_analysis_cleaned": (
                _analyse_output(
                    enhanced_cleaned_output,
                    documents,
                )
            ),
            "validation": enhanced_result.get(
                "validation",
                {},
            ),
            "quality": enhanced_result.get(
                "quality",
                {},
            ),
            "display_sources": enhanced_result.get(
                "sources",
                [],
            ),
        },
        "poc_prompt_same_evidence": {
            "system_prompt": poc_system_prompt,
            "user_prompt": poc_user_prompt,
            "system_prompt_characters": len(
                poc_system_prompt
            ),
            "user_prompt_characters": len(
                poc_user_prompt
            ),
            "prompt_rule_checks": (
                _prompt_rule_checks(
                    poc_system_prompt
                    + "\n"
                    + poc_user_prompt
                )
            ),
            "raw_model_output": poc_raw_output,
            "output_analysis": _analyse_output(
                poc_raw_output,
                documents,
            ),
        },
    }

    timestamped_path = output_directory / (
        f"mpmd_generation_parity_{run_timestamp}.json"
    )
    latest_path = output_directory / (
        "mpmd_generation_parity_latest.json"
    )

    json_text = json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
        default=str,
    )

    timestamped_path.write_text(
        json_text,
        encoding="utf-8",
    )
    latest_path.write_text(
        json_text,
        encoding="utf-8",
    )

    separator = "=" * 100

    print("\n" + separator)
    print("CONTROLLED HANS GENERATION PARITY TEST")
    print(separator)
    print(
        "Same input + same final documents + same local model "
        "+ same temperature."
    )
    print(
        "Only the generation prompt differs."
    )

    print("\nTOPIC CHECK")
    print("-" * 100)
    print(
        "Captured:",
        sorted(enhanced_topic_ids),
    )
    print(
        "Expected:",
        sorted(EXPECTED_TOPICS),
    )
    print(
        "Exact topic match:",
        enhanced_topic_ids == EXPECTED_TOPICS,
    )

    print("\nFINAL DOCUMENTS SENT TO BOTH PROMPTS")
    print("-" * 100)

    for summary in document_summaries:
        print(
            f"Doc {summary['doc_number']}: "
            f"{summary['title']}"
        )
        print(
            f"  URL: {summary['url']}"
        )
        print(
            f"  Type: {summary['object_type']}"
        )
        print(
            f"  Full content characters: "
            f"{summary['content_characters']}"
        )

    print("\nPROMPT CONTENT VISIBILITY")
    print("-" * 100)

    for item in prompt_visibility:
        print(
            f"Doc {item['doc_number']}: "
            f"full={item['full_content_characters']} | "
            f"enhanced visible prefix≈"
            f"{item['estimated_prefix_in_enhanced_prompt']} | "
            f"PoC visible prefix≈"
            f"{item['estimated_prefix_in_poc_prompt']}"
        )

    print("\nSTUDY-FORMAT WORDING FOUND IN EVIDENCE")
    print("-" * 100)

    if not evidence_format_audit:
        print(
            "No study-format wording was found in the final "
            "document text."
        )
    else:
        for item in evidence_format_audit:
            print(
                f"\nDoc {item['doc_number']}: "
                f"{item['title']}"
            )

            for match in item["matches"]:
                print(
                    f"  [{match['keyword']}] "
                    f"{match['snippet']}"
                )

    enhanced_analysis = report[
        "enhanced_deployment"
    ]["output_analysis_cleaned"]
    poc_analysis = report[
        "poc_prompt_same_evidence"
    ]["output_analysis"]

    print("\nENHANCED PROMPT — RAW MODEL OUTPUT")
    print("-" * 100)
    print(enhanced_raw_output)

    print("\nENHANCED SERVICE — FINAL CLEANED OUTPUT")
    print("-" * 100)
    print(enhanced_cleaned_output)

    print("\nPoC PROMPT — SAME MODEL AND SAME EVIDENCE")
    print("-" * 100)
    print(poc_raw_output)

    print("\nAUTOMATIC COMPARISON")
    print("-" * 100)
    print(
        "Enhanced grouped citation:",
        enhanced_analysis["grouped_citation_found"],
    )
    print(
        "PoC grouped citation:",
        poc_analysis["grouped_citation_found"],
    )
    print(
        "Enhanced unsupported study-format risk:",
        enhanced_analysis[
            "unsupported_study_format_risk"
        ],
    )
    print(
        "PoC unsupported study-format risk:",
        poc_analysis[
            "unsupported_study_format_risk"
        ],
    )
    print(
        "Enhanced unasked-content flags:",
        enhanced_analysis["unasked_content_flags"],
    )
    print(
        "PoC unasked-content flags:",
        poc_analysis["unasked_content_flags"],
    )
    print(
        "Enhanced topic coverage:",
        enhanced_analysis["topic_coverage_count"],
        "/ 4",
    )
    print(
        "PoC topic coverage:",
        poc_analysis["topic_coverage_count"],
        "/ 4",
    )

    print("\nFILES WRITTEN")
    print("-" * 100)
    print(timestamped_path)
    print(latest_path)

    print("\nINTERPRETATION GUIDE")
    print("-" * 100)
    print(
        "1. If both outputs make the same unsupported claim, "
        "the evidence wording/model is the main problem."
    )
    print(
        "2. If only the enhanced output fails, the first divergence "
        "is the enhanced prompt or its evidence formatting."
    )
    print(
        "3. If only the PoC output fails, keep the enhanced prompt "
        "and refine the specific ignored rule rather than reverting."
    )
    print(
        "4. If the requested fact is absent from the evidence audit, "
        "the correct answer is an explicit uncertainty statement, "
        "not a confident on-campus/hybrid label."
    )


if __name__ == "__main__":
    asyncio.run(main())
