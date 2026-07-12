from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

import psycopg

from app.email.disclaimer import append_disclaimer_to_draft
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

        followup_start = time.perf_counter()

        followup_type = classify_followup_email(
            email_text,
            has_thread_memory=bool(previous_context),
        )

        timing["followup_detection"] = (
            time.perf_counter() - followup_start
        )

        if followup_type == "clarification_or_complaint":
            draft = build_followup_flag_message(email_text)

            return {
                "is_followup": True,
                "followup_type": followup_type,
                "flagged_for_human": True,
                "thread_id": thread_key,
                "email_context": {},
                "detected_topics": [],
                "staff_draft": append_disclaimer_to_draft(draft),
                "citations": [],
                "sources": [],
                "validation": {
                    "is_grounded": False,
                    "citations_valid": False,
                    "has_hallucinations": False,
                    "confidence": 0.0,
                    "failure_type": "followup_requires_human_review",
                },
                "quality": {
                    "quality_score": 0,
                    "quality_label": "review",
                    "review_required": True,
                    "review_reason": (
                        "Clarification or complaint requires direct staff review"
                    ),
                    "citation_count": 0,
                },
                "timing": {
                    **timing,
                    "total": time.perf_counter() - overall_start,
                },
            }

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

        context_start = time.perf_counter()

        email_context = extract_email_context(enriched_email)

        matched_programme = (
            programme_match.get("program_name")
            or programme_match.get("matched_programme")
            or ""
        )

        if matched_programme:
            email_context["target_program"] = matched_programme
            email_context["matched_programme"] = matched_programme

        matched_url = programme_match.get("url") or ""

        if matched_url:
            email_context["target_program_url"] = matched_url
            email_context["matched_programme_url"] = matched_url

        application_url = (
            programme_match.get("application_url") or ""
        )

        if application_url:
            email_context[
                "target_program_application_url"
            ] = application_url

        email_context = merge_context_with_thread(
            email_context,
            previous_context,
        )

        topics = detect_topics(
            enriched_email,
            email_context,
            max_topics=6,
        )

        timing["context_and_topics"] = (
            time.perf_counter() - context_start
        )

        retrieval_start = time.perf_counter()

        all_documents: List[Dict[str, Any]] = []
        topic_results: List[Dict[str, Any]] = []

        for topic in topics:
            topic_id = str(topic.get("topic_id", ""))

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

            retrieved = retrieve_for_topic(
                connection=self.connection,
                query=evidence_query,
                top_k=max(top_k, 5),
            )

            official_documents = get_official_programme_docs(
                context=email_context,
                topic_id=topic_id,
                max_docs=3,
            )

            combined = official_documents + retrieved

            filtered = filter_docs_for_programme(
                combined,
                email_context,
                topic_id=topic_id,
                min_keep=3,
            )

            topic["query"] = evidence_query
            topic["source_count"] = len(filtered)

            topic_results.append(topic)
            all_documents.extend(filtered)

        all_documents = deduplicate_documents(
            all_documents,
            limit=max(settings.final_source_limit * 2, 12),
        )

        resolved_documents, conflicts = (
            detect_and_resolve_conflicts(all_documents)
        )

        final_documents = resolved_documents[
            : settings.final_source_limit
        ]

        timing["retrieval"] = (
            time.perf_counter() - retrieval_start
        )

        generation_start = time.perf_counter()

        if final_documents:
            user_prompt = build_email_user_prompt(
                original_email=email_text,
                email_context=email_context,
                topics=topic_results,
                documents=final_documents,
            )

            draft = await self.llm.generate(
                system_prompt=build_email_system_prompt(),
                user_prompt=user_prompt,
                temperature=0.1,
            )
        else:
            draft = (
                "Dear applicant,\n\n"
                "Thank you for your enquiry.\n\n"
                "I could not confirm the requested information "
                "from the available official sources. "
                "Please review this enquiry manually before replying.\n\n"
                "Kind regards,\n"
                "HTW Berlin Student Services"
            )

        draft = clean_staff_draft(
            draft,
            email_context,
        )

        draft = fix_application_fee_confusion(
            draft,
            topic_results,
            final_documents,
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
            email_context,
        )

        timing["generation"] = (
            time.perf_counter() - generation_start
        )

        validation_start = time.perf_counter()

        validation = validate_email_draft(
            draft=draft,
            documents=display_documents,
            topics=topic_results,
            email_context=email_context,
        )

        review_required = (
            validation["review_required"]
            or settings.staff_review_required_for_all
        )

        review_reasons = []

        if validation.get("review_reason"):
            review_reasons.append(
                validation["review_reason"]
            )

        if settings.staff_review_required_for_all:
            review_reasons.append(
                "All HANS drafts require staff review before sending"
            )

        review_reason = "; ".join(
            dict.fromkeys(review_reasons)
        )

        quality_score = round(
            float(validation.get("confidence", 0.0)) * 100
        )

        quality_label = (
            "review"
            if validation["review_required"]
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
            "citation_count": validation["citation_count"],
            "citations": validation["citations"],
        }

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

        sources = []

        for document in display_documents:
            sources.append(
                {
                    "id": str(document.get("id", "")),
                    "title": document.get("title", ""),
                    "url": (
                        document.get("source_url")
                        or document.get("url")
                        or ""
                    ),
                    "type": document.get("object_type", ""),
                    "last_updated": document.get(
                        "last_updated",
                        "",
                    ),
                    "excerpt": (
                        document.get("content", "")[:300]
                    ),
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
            "citations": validation["citations"],
            "sources": sources,
            "validation": {
                key: validation[key]
                for key in [
                    "is_grounded",
                    "citations_valid",
                    "has_hallucinations",
                    "confidence",
                    "failure_type",
                ]
            },
            "quality": quality,
            "conflicts": conflicts,
            "timing": timing,
            "automatic_send": False,
        }