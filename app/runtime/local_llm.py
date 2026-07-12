from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

import httpx

from app.settings import settings


logger = logging.getLogger(__name__)


class LocalLLMError(RuntimeError):
    pass


def _remove_thinking_block(text: str) -> str:
    cleaned = re.sub(
        r"<think>.*?</think>",
        "",
        text or "",
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


class HTWOllamaClient:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self.verify_ssl = settings.verify_ssl

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        if not self.base_url:
            raise LocalLLMError("Ollama base URL is not configured.")

        payload = {
            "model": self.model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt + "\n/no_think",
                },
            ],
            "options": {
                "temperature": temperature,
            },
        }

        url = f"{self.base_url}/api/chat"

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.exception("HTW Ollama request failed")
            raise LocalLLMError(
                f"HTW model request failed: {exc}"
            ) from exc

        data: Dict[str, Any] = response.json()

        message = data.get("message", {})
        content = message.get("content", "")

        if not content:
            raise LocalLLMError(
                "HTW model returned an empty response."
            )

        return _remove_thinking_block(content)


def build_email_system_prompt() -> str:
    return """
You are HANS, the HTW Berlin AI-assisted email drafting system.

Your task is to prepare one staff-ready email draft in response to a prospective or current student's enquiry.

Mandatory rules:

1. The draft is for HTW Berlin staff review. It must never claim to be a final or binding admission decision.

2. Use only the evidence documents provided in the prompt. Do not use general knowledge and do not invent missing facts.

3. Answer every detected topic from the student's message, but do not introduce unrelated topics.

4. When the evidence does not support a conclusion, state clearly that the information could not be confirmed from the available official sources.

5. Programme-specific questions must be answered using programme-specific evidence whenever available.

6. Do not classify an applicant's formal eligibility. Explain the documented requirements and state that the official application review determines eligibility.

7. Include citations in the form [Doc 1], [Doc 2] immediately after the factual claim they support.

8. Use simple, polite and professional language.

9. Preserve the language of the incoming email. Use English for English emails and German for German emails.

10. Start with an appropriate greeting. Use the student's first name only when it was clearly identified.

11. End with:
Kind regards,
HTW Berlin Student Services

For a German draft, end with:
Mit freundlichen Grüßen
Studierendenservice der HTW Berlin

12. Do not include a separate reference-link section. The application adds that after generation.

13. Do not include the system disclaimer. The application adds it after generation.

14. Do not mention internal processes such as vector search, retrieval, model confidence or topic detection.

15. Keep the draft easy for a staff member to verify and edit.
""".strip()


def build_email_user_prompt(
    *,
    original_email: str,
    email_context: Dict[str, Any],
    topics: List[Dict[str, Any]],
    documents: List[Dict[str, Any]],
) -> str:
    profile_lines = []

    context_labels = {
        "student_name": "Student name",
        "previous_degree": "Previous/current degree",
        "target_degree": "Target degree",
        "target_program": "Target programme",
        "country": "Country/background",
        "citizenship_group": "Citizenship category",
        "residence_country": "Residence country",
        "target_program_url": "Programme URL",
        "target_program_application_url": "Programme application URL",
    }

    for key, label in context_labels.items():
        value = email_context.get(key)
        if value:
            profile_lines.append(f"- {label}: {value}")

    topic_lines = []
    for topic in topics:
        topic_lines.append(
            f"- {topic.get('label')}: "
            f"{topic.get('base_query') or topic.get('query')}"
        )

    evidence_blocks = []

    for index, document in enumerate(documents, start=1):
        title = document.get("title", "")
        url = (
            document.get("source_url")
            or document.get("url")
            or ""
        )
        content = (
            document.get("content")
            or document.get("chunk_text")
            or ""
        )
        object_type = document.get("object_type", "")
        last_updated = document.get("last_updated", "")

        evidence_blocks.append(
            "\n".join(
                [
                    f"[Doc {index}]",
                    f"Title: {title}",
                    f"URL: {url}",
                    f"Type: {object_type}",
                    f"Last updated: {last_updated}",
                    "Content:",
                    content[:1800],
                ]
            )
        )

    return f"""
ORIGINAL EMAIL
--------------
{original_email}

INTERPRETED CONTEXT
-------------------
{chr(10).join(profile_lines) if profile_lines else "- No reliable profile details detected."}

TOPICS THAT MUST BE ANSWERED
----------------------------
{chr(10).join(topic_lines)}

OFFICIAL EVIDENCE
-----------------
{chr(10).join(evidence_blocks)}

Create one complete staff-ready email draft.

Important:
- Cover every listed topic.
- Use programme-specific evidence first.
- Use [Doc N] citations after factual claims.
- Do not make unsupported assumptions.
- Do not write a reference-link list.
- Do not write a disclaimer.
""".strip()